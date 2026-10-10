; Transform only kernel; main independently checks all 65,536 pairs.
target triple = "x86_64-pc-windows-msvc"
define i8 @kernel(i8 %x, i8 %y) noinline {
entry:
  %sum = add i8 %x, %y
  %difference = sub i8 %sum, %y
  %result = xor i8 %difference, %y
  ret i8 %result
}
define i32 @main() {
entry:
  br label %loop
loop:
  %index = phi i32 [ 0, %entry ], [ %next, %check ]
  %x = trunc i32 %index to i8
  %shift = lshr i32 %index, 8
  %y = trunc i32 %shift to i8
  %actual = call i8 @kernel(i8 %x, i8 %y)
  %expected = xor i8 %x, %y
  %equal = icmp eq i8 %actual, %expected
  br i1 %equal, label %check, label %failure
check:
  %next = add i32 %index, 1
  %done = icmp eq i32 %next, 65536
  br i1 %done, label %success, label %loop
success:
  ret i32 0
failure:
  ret i32 1
}
