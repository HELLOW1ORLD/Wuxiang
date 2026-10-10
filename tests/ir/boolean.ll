; i1 add/sub cannot use shift-by-one identities: that shift is poison.
target triple = "x86_64-pc-windows-msvc"
define i1 @boolean(i1 %x, i1 %y) noinline {
  %result = add i1 %x, %y
  ret i1 %result
}
define i32 @main() {
  %a = call i1 @boolean(i1 false, i1 false)
  %b = call i1 @boolean(i1 false, i1 true)
  %c = call i1 @boolean(i1 true, i1 false)
  %d = call i1 @boolean(i1 true, i1 true)
  %nb = xor i1 %b, true
  %nc = xor i1 %c, true
  %ab = or i1 %a, %nb
  %cd = or i1 %nc, %d
  %failed = or i1 %ab, %cd
  %exit = zext i1 %failed to i32
  ret i32 %exit
}
