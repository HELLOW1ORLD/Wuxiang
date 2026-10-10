#include "shared.h"
uint64_t Derived::value(uint64_t x) const {return core(x)^number;}
Base* make_object(uint64_t n){return new Derived(n);}
void delete_object(Base* p){delete p;}
uint64_t via_callback(Callback cb,uint64_t x){return cb(x)^core(x);}
void clang_throw(int n){struct Guard {~Guard(){destructor_callback();}} guard; if(n)throw std::runtime_error("cross-module");}
std::vector<std::string> exchange(std::vector<std::string> v){v.emplace_back("clang");return v;}
int clang_catch(Callback cb){try{cb(1);return 0;}catch(const std::runtime_error& e){return std::string(e.what())=="msvc"?91:0;}}
Box<uint64_t> exchange_box(Box<uint64_t> b){return Box<uint64_t>{b.twice()};}
WUXIANG_PROTECT uint64_t core(uint64_t x){
  for(unsigned i=0;i<WUXIANG_COMPAT_ROUNDS;++i){x^=x>>17;x*=0xed5ad4bbU;x^=x>>11;x*=0xac4c1b51U;x^=x>>15;}
  return x;
}
