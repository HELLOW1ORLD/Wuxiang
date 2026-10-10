; Adding volatile operations invalidates inferred memory/speculation attributes.
target triple = "x86_64-pc-windows-msvc"
define i32 @effect(i32 %x, i32 %y) nosync speculatable memory(none) {
entry:
  %sum = add i32 %x, %y
  %result = xor i32 %sum, 91
  ret i32 %result
}
define i32 @main() {
  %unused = call i32 @effect(i32 3, i32 4) nosync speculatable memory(none)
  ret i32 0
}
