; Flags that constrain overflow must remain intact and are not substituted.
target triple = "x86_64-pc-windows-msvc"
define i32 @flagged(i32 %x, i32 %y) {
entry:
  %sum = add nsw i32 %x, %y
  ret i32 %sum
}
