; Structural rewrites must not break loop PHIs or caller-visible memory writes.
target triple = "x86_64-pc-windows-msvc"
define i32 @loop_kernel(ptr %memory, i32 %length) noinline {
entry:
  %limit = and i32 %length, 255
  %empty = icmp eq i32 %limit, 0
  br i1 %empty, label %exit, label %loop
loop:
  %index = phi i32 [ 0, %entry ], [ %next, %loop ]
  %accumulator = phi i32 [ 0, %entry ], [ %sum, %loop ]
  %sum = add i32 %accumulator, %index
  %next = add i32 %index, 1
  %done = icmp eq i32 %next, %limit
  br i1 %done, label %exit, label %loop
exit:
  %result = phi i32 [ 0, %entry ], [ %sum, %loop ]
  store i32 %result, ptr %memory
  ret i32 %result
}
define i32 @main() {
entry:
  %memory = alloca i32, align 4
  br label %test
test:
  %length = phi i32 [ 0, %entry ], [ %next, %check ]
  %actual = call i32 @loop_kernel(ptr %memory, i32 %length)
  %before = sub i32 %length, 1
  %product = mul i32 %length, %before
  %expected = udiv i32 %product, 2
  %stored = load i32, ptr %memory
  %return_ok = icmp eq i32 %actual, %expected
  %memory_ok = icmp eq i32 %stored, %expected
  %correct = and i1 %return_ok, %memory_ok
  br i1 %correct, label %check, label %failure
check:
  %next = add i32 %length, 1
  %done = icmp eq i32 %next, 256
  br i1 %done, label %success, label %test
success:
  ret i32 0
failure:
  ret i32 1
}
