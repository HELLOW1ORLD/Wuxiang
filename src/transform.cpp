#include "llvm/ADT/SmallVector.h"
#include "llvm/Analysis/ValueTracking.h"
#include "llvm/Analysis/LoopInfo.h"
#include "llvm/Bitcode/BitcodeWriter.h"
#include "llvm/IR/Constants.h"
#include "llvm/IR/Dominators.h"
#include "llvm/IR/GlobalAlias.h"
#include "llvm/IR/IRBuilder.h"
#include "llvm/IR/IntrinsicInst.h"
#include "llvm/IR/Module.h"
#include "llvm/IR/Verifier.h"
#include "llvm/IRReader/IRReader.h"
#include "llvm/Support/CommandLine.h"
#include "llvm/Support/FileSystem.h"
#include "llvm/Support/FormatVariadic.h"
#include "llvm/Support/JSON.h"
#include "llvm/Support/SourceMgr.h"
#include "llvm/Support/raw_ostream.h"
#include <algorithm>
#include <cctype>
#include <cstdint>
#include <random>
#include <set>
#include <string>
#include <vector>

using namespace llvm;
static cl::opt<std::string> Input(cl::Positional, cl::Required, cl::desc("Input LLVM IR or bitcode"));
static cl::opt<std::string> Output("o", cl::Required, cl::desc("Output bitcode"));
static cl::opt<std::string> Report("report", cl::Required, cl::desc("Coverage JSON"));
static cl::opt<uint64_t> Seed("seed", cl::init(1), cl::desc("Diversification seed"));
static cl::opt<std::string> Functions("functions", cl::init(""), cl::desc("Comma-separated exact LLVM symbol names"));
static cl::opt<std::string> Mode("mode", cl::init("balanced"));
static cl::opt<std::string> SurfaceSymbol("surface-symbol", cl::init(""));
static cl::opt<std::string> SurfaceOffsets("surface-offsets", cl::init(""));
static void invalidateMemoryFacts(Function &F);

static void addSurfaceReferences(Function &F, ArrayRef<uint64_t> Offsets) {
  Module &M = *F.getParent();
  auto *Byte = Type::getInt8Ty(M.getContext());
  auto *Data = M.getNamedGlobal(SurfaceSymbol.getValue());
  if (!Data)
    Data = new GlobalVariable(M, Byte, true, GlobalValue::ExternalLinkage,
                              nullptr, SurfaceSymbol.getValue());
  // Keep the text pointer visible as an argument to a separate noinline reader.
  // The generated noexcept C++ reader only performs a volatile byte read.
  auto *ReaderType = FunctionType::get(Type::getVoidTy(M.getContext()),
                                      {PointerType::getUnqual(M.getContext())}, false);
  FunctionCallee Reader = M.getOrInsertFunction(SurfaceSymbol.getValue() + "_read", ReaderType);
  auto *ReaderFunction = cast<Function>(Reader.getCallee());
  ReaderFunction->addFnAttr(Attribute::NoUnwind);
  ReaderFunction->addFnAttr(Attribute::WillReturn);
  IRBuilder<> B(&*F.getEntryBlock().getFirstInsertionPt());
  for (uint64_t Offset : Offsets) {
    // Non-inbounds GEP: the external array is defined in a separate COFF object.
    auto *Pointer = B.CreateGEP(Byte, Data, B.getInt64(Offset), "wx.hint.address");
    auto *Call = B.CreateCall(Reader, {Pointer});
    Call->setDoesNotThrow();
  }
  invalidateMemoryFacts(F);
}

static void annotationNames(Module &M, std::set<std::string> &Names) {
  auto *G = M.getGlobalVariable("llvm.global.annotations");
  if (!G || !G->hasInitializer()) return;
  auto *A = dyn_cast<ConstantArray>(G->getInitializer());
  if (!A) return;
  for (Value *V : A->operands()) {
    auto *S = dyn_cast<ConstantStruct>(V);
    if (!S || S->getNumOperands() < 2) continue;
    auto *F = dyn_cast<Function>(S->getOperand(0)->stripPointerCasts());
    auto *Text = dyn_cast<GlobalVariable>(getUnderlyingObject(S->getOperand(1)));
    if (!F || !Text || !Text->hasInitializer()) continue;
    auto *Bytes = dyn_cast<ConstantDataArray>(Text->getInitializer());
    if (Bytes && Bytes->isCString() && Bytes->getAsCString() == "wuxiang.protect")
      Names.insert(F->getName().str());
  }
}

static bool integerCandidate(Instruction &I) {
  auto *Op = dyn_cast<BinaryOperator>(&I);
  if (!Op || !Op->getType()->isIntegerTy()) return false;
  if (cast<IntegerType>(Op->getType())->getBitWidth() < 2) return false;
  if (Op->getOpcode() != Instruction::Add && Op->getOpcode() != Instruction::Sub &&
      Op->getOpcode() != Instruction::Xor) return false;
  // Dropping flags would change poison semantics. Leave constrained arithmetic.
  if (Op->hasNoSignedWrap() || Op->hasNoUnsignedWrap()) return false;
  return true;
}

static void invalidateMemoryFacts(Function &F) {
  F.setMemoryEffects(MemoryEffects::unknown());
  F.removeFnAttr(Attribute::NoSync);
  F.removeFnAttr(Attribute::Speculatable);
  for (Function &Caller : *F.getParent()) for (BasicBlock &BB : Caller)
    for (Instruction &I : BB) if (auto *Call = dyn_cast<CallBase>(&I)) {
      Value *Target = Call->getCalledOperand()->stripPointerCasts();
      if (auto *Alias = dyn_cast<GlobalAlias>(Target)) Target = Alias->getAliaseeObject();
      if (Target == &F) {
        Call->setMemoryEffects(MemoryEffects::unknown());
        Call->removeFnAttr(Attribute::NoSync);
        Call->removeFnAttr(Attribute::Speculatable);
      }
    }
}

static void substitute(BinaryOperator &Op, uint64_t Choice) {
  IRBuilder<> B(&Op);
  B.SetCurrentDebugLocation(Op.getDebugLoc());
  // Freeze once so duplicated operands do not introduce independently chosen
  // undef values. This is a refinement of poison/undef, never new poison.
  Value *X = B.CreateFreeze(Op.getOperand(0), "wx.x");
  Value *Y = B.CreateFreeze(Op.getOperand(1), "wx.y");
  if (Op.getFunction()->hasPersonalityFn()) {
    IRBuilder<> Entry(&*Op.getFunction()->getEntryBlock().getFirstInsertionPt());
    auto *Mask = Entry.CreateAlloca(Op.getType(), nullptr, "wx.eh.mask");
    B.CreateStore(ConstantInt::get(Op.getType(), Choice | 1), Mask)->setVolatile(true);
    auto *First = B.CreateLoad(Op.getType(), Mask, "wx.eh.mask.first");
    First->setVolatile(true);
    X = B.CreateAdd(X, First);
    auto *Second = B.CreateLoad(Op.getType(), Mask, "wx.eh.mask.second");
    Second->setVolatile(true);
    X = B.CreateSub(X, Second);
    invalidateMemoryFacts(*Op.getFunction());
  }
  Value *R = nullptr;
  if (Op.getOpcode() == Instruction::Xor) {
    R = B.CreateAnd(B.CreateOr(X, Y), B.CreateNot(B.CreateAnd(X, Y)), "wx.xor");
  } else {
    if (Op.getOpcode() == Instruction::Sub) {
      Y = B.CreateNot(Y);
      X = B.CreateAdd(X, ConstantInt::get(Op.getType(), 1));
    }
    if (Choice & 1)
      R = B.CreateSub(B.CreateShl(B.CreateOr(X, Y), ConstantInt::get(Op.getType(), 1)),
                      B.CreateXor(X, Y), "wx.sum");
    else
      R = B.CreateAdd(B.CreateXor(X, Y),
                      B.CreateShl(B.CreateAnd(X, Y), ConstantInt::get(Op.getType(), 1)), "wx.sum");
  }
  Op.replaceAllUsesWith(R);
  Op.eraseFromParent();
}

static bool unsupported(Function &F, json::Array &Reasons) {
  bool Bad = false;
  if (F.hasPersonalityFn()) {
    StringRef P = F.getPersonalityFn()->stripPointerCasts()->getName();
    if (P.contains("C_specific_handler") || P.contains("except_handler")) {
      Reasons.push_back("SEH is outside the v1 support contract"); Bad = true;
    }
  }
  for (BasicBlock &BB : F) for (Instruction &I : BB) {
    if (auto *C = dyn_cast<CallBase>(&I)) {
      if (C->isInlineAsm()) { Reasons.push_back("inline assembly is unsupported"); Bad = true; }
      if (Function *Callee = C->getCalledFunction())
        if (Callee->getName().starts_with("llvm.coro.")) {
          Reasons.push_back("coroutines are unsupported"); Bad = true;
        }
    }
    if (isa<IndirectBrInst>(I) || isa<CallBrInst>(I)) {
      Reasons.push_back("indirect control-flow region is unsupported"); Bad = true;
    }
  }
  return Bad;
}

static bool addRegion(Function &F, std::mt19937_64 &Rng) {
  // EH functions retain their original blocks, funclets, operand bundles and
  // unwind graph. Arithmetic substitutions above introduce no calls or traps.
  if (F.hasPersonalityFn()) return false;
  DominatorTree DT(F);
  LoopInfo LI(DT);
  std::vector<Instruction *> Points;
  std::vector<Instruction *> Fallback;
  for (BasicBlock &BB : F) {
    if (BB.isEHPad() || LI.getLoopFor(&BB)) continue;
    unsigned Count = 0;
    Instruction *First = nullptr;
    for (Instruction &I : BB) {
      if (isa<PHINode>(I) || isa<AllocaInst>(I) || I.isTerminator()) continue;
      if (!First) First = &I;
      if (++Count >= 2) Points.push_back(&I);
    }
    // Optimized parsers often have only one entry comparison before a branch.
    // Such an ordinary branch region is still a valid outside-loop site.
    auto *Branch = dyn_cast<BranchInst>(BB.getTerminator());
    if (Count == 1 && First && Branch && Branch->isConditional()) Fallback.push_back(First);
  }
  if (Points.empty()) Points = std::move(Fallback);
  if (Points.empty()) return false;
  Instruction *At = Points[Rng() % Points.size()];
  BasicBlock *Head = At->getParent();
  BasicBlock *Tail = Head->splitBasicBlock(At->getIterator(), "wx.continue");
  LLVMContext &C = F.getContext();
  BasicBlock *True = BasicBlock::Create(C, "wx.route.a", &F, Tail);
  BasicBlock *False = BasicBlock::Create(C, "wx.route.b", &F, Tail);
  IRBuilder<> Entry(&*F.getEntryBlock().getFirstInsertionPt());
  auto *Cell = Entry.CreateAlloca(Type::getInt32Ty(C), nullptr, "wx.route");
  Cell->setAlignment(Align(4));
  uint32_t Key = static_cast<uint32_t>(Rng());
  auto *K = ConstantInt::get(Type::getInt32Ty(C), Key);
  auto *Term = Head->getTerminator();
  IRBuilder<> B(Term);
  B.CreateStore(K, Cell)->setVolatile(true);
  auto *Load = B.CreateLoad(Type::getInt32Ty(C), Cell, "wx.route.value");
  Load->setVolatile(true);
  B.CreateCondBr(B.CreateICmpEQ(Load, K), True, False);
  Term->eraseFromParent();
  IRBuilder<> BT(True);
  BT.CreateBr(Tail);
  IRBuilder<> BF(False);
  BF.CreateStore(ConstantInt::get(Type::getInt32Ty(C), Key ^ 0x85ebca6bU), Cell)->setVolatile(true);
  BF.CreateBr(Tail);
  invalidateMemoryFacts(F);
  return true;
}

static bool writeReport(json::Object Root) {
  std::error_code EC;
  raw_fd_ostream OS(Report, EC, sys::fs::OF_Text);
  if (EC) { errs() << "Cannot write report: " << EC.message() << '\n'; return false; }
  OS << formatv("{0:2}", json::Value(std::move(Root))) << '\n';
  OS.flush();
  return !OS.has_error();
}

int main(int argc, char **argv) {
  cl::ParseCommandLineOptions(argc, argv, "Wuxiang bounded LLVM IR protection\n");
  json::Array Results, Errors;
  LLVMContext Context;
  SMDiagnostic Diagnostic;
  auto M = parseIRFile(Input, Diagnostic, Context);
  if (!M) {
    Diagnostic.print(argv[0], errs());
    writeReport(json::Object{{"schema_version", 1}, {"ok", false}, {"errors", json::Array{"input IR parsing failed"}}});
    return 2;
  }
  if (Mode != "balanced") Errors.push_back("Only balanced mode is supported");
  SmallVector<uint64_t> HintOffsets;
  if (SurfaceSymbol.getValue().empty() != SurfaceOffsets.getValue().empty())
    Errors.push_back("Surface symbol and offsets must be specified together");
  if (!SurfaceSymbol.getValue().empty()) {
    const std::string &S = SurfaceSymbol.getValue();
    if (S.size() > 64 || !(std::isalpha(static_cast<unsigned char>(S[0])) || S[0] == '_') ||
        !std::all_of(S.begin(), S.end(), [](unsigned char C) {
          return C < 128 && (std::isalnum(C) || C == '_');
        })) Errors.push_back("Invalid surface symbol");
    if (M->getNamedValue(S) || M->getNamedValue(S + "_read"))
      Errors.push_back("Surface symbol collides with input module");
    SmallVector<StringRef> Parts;
    StringRef(SurfaceOffsets.getValue()).split(Parts, ',');
    for (StringRef Part : Parts) {
      uint64_t Offset = 0;
      if (Part.empty() || Part.getAsInteger(10, Offset) || Offset > 65535)
        Errors.push_back("Invalid surface offset");
      else HintOffsets.push_back(Offset);
    }
    if (HintOffsets.size() > 16) Errors.push_back("Too many surface references");
  }
  std::set<std::string> Names;
  annotationNames(*M, Names);
  SmallVector<StringRef> Explicit;
  StringRef(Functions.getValue()).split(Explicit, ',', -1, false);
  for (StringRef N : Explicit) if (!N.trim().empty()) Names.insert(N.trim().str());
  if (Names.empty()) Errors.push_back("No annotated or explicitly selected functions");
  std::mt19937_64 Rng(Seed);
  for (const std::string &Name : Names) {
    json::Array Reasons;
    Function *F = M->getFunction(Name);
    int64_t Ints = 0, Regions = 0, Hints = 0;
    int64_t OriginalBlocks = F ? static_cast<int64_t>(F->size()) : 0;
    int64_t EligibleIntegers = 0;
    std::string Status = "unsupported";
    if (!F || F->isDeclaration()) {
      Reasons.push_back("Selected definition not found; select an exact surviving LLVM symbol");
      Errors.push_back("Missing function: " + Name);
    } else if (unsupported(*F, Reasons)) {
      Errors.push_back("Unsupported function: " + Name);
    } else {
      SmallVector<BinaryOperator *> Candidates;
      for (BasicBlock &BB : *F) for (Instruction &I : BB)
        if (integerCandidate(I)) Candidates.push_back(cast<BinaryOperator>(&I));
      EligibleIntegers = static_cast<int64_t>(Candidates.size());
      // A bounded one-site budget deliberately avoids expensive full flattening.
      if (!Candidates.empty()) {
        substitute(*Candidates[Rng() % Candidates.size()], Rng()); Ints = 1;
      }
      Regions = addRegion(*F, Rng) ? 1 : 0;
      if (F->hasPersonalityFn()) Reasons.push_back("EH function: structural transformations skipped conservatively");
      if (Candidates.size() > 1) Reasons.push_back("Balanced budget: additional eligible arithmetic sites remain unchanged");
      if (!Ints && !Regions) {
        Reasons.push_back("No transformable site survived optimization");
        Errors.push_back("Untransformable function: " + Name);
      } else {
        if (!HintOffsets.empty() && Errors.empty()) {
          addSurfaceReferences(*F, HintOffsets);
          Hints = static_cast<int64_t>(HintOffsets.size());
        }
        F->addFnAttr(Attribute::NoInline);
        Reasons.push_back("V1 transforms bounded sites; it does not cover the entire function");
        Status = "partial";
      }
    }
    Results.push_back(json::Object{{"name", Name}, {"status", Status},
      {"transformations", json::Object{{"integer_substitutions", Ints}, {"block_splits", Regions}, {"control_regions", Regions}, {"surface_references", Hints}}},
      {"coverage", json::Object{{"original_blocks", OriginalBlocks}, {"rewritten_blocks", Regions},
        {"eligible_integer_sites", EligibleIntegers}, {"rewritten_integer_sites", Ints}, {"whole_function", false}}},
      {"reasons", std::move(Reasons)}});
  }
  bool Verified = !verifyModule(*M, &errs());
  if (!Verified) Errors.push_back("LLVM verifier rejected transformed module");
  bool OK = Errors.empty();
  if (OK) {
    std::error_code EC;
    raw_fd_ostream OS(Output, EC, sys::fs::OF_None);
    if (EC) { Errors.push_back("Cannot write output: " + EC.message()); OK = false; }
    else { WriteBitcodeToFile(*M, OS); OS.flush(); if (OS.has_error()) { Errors.push_back("Output write failed"); OK = false; } }
  }
  bool ReportOK = writeReport(json::Object{{"schema_version", 1}, {"ok", OK}, {"verified", Verified},
    {"seed", std::to_string(Seed.getValue())}, {"mode", Mode.getValue()}, {"functions", std::move(Results)}, {"errors", std::move(Errors)}});
  return OK && ReportOK ? 0 : 1;
}
