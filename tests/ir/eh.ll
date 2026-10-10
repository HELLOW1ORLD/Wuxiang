; Personality conservatively disables structural rewrites even for entry.
target triple = "x86_64-pc-windows-msvc"
declare i32 @__CxxFrameHandler3(...)
define i32 @with_eh(i32 %x, i32 %y) personality ptr @__CxxFrameHandler3 {
entry:
  %sum = add i32 %x, %y
  ret i32 %sum
}
