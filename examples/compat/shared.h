#pragma once
#include <cstdint>
#include <string>
#include <vector>
#include <stdexcept>
#include "wuxiang/protect.h"
#include "constants.inc"
struct Base { virtual ~Base() = default; virtual uint64_t value(uint64_t) const = 0; };
struct Side { virtual ~Side() = default; virtual int marker() const { return 71; } };
struct Derived : virtual Base, Side {
  explicit Derived(uint64_t n):number(n){}
  uint64_t value(uint64_t x) const override;
  uint64_t number;
};
template<class T> struct Box { T value; T twice() const { return value+value; } };
Box<uint64_t> exchange_box(Box<uint64_t>);
using Callback = uint64_t(*)(uint64_t);
Base* make_object(uint64_t);
void delete_object(Base*);
uint64_t via_callback(Callback,uint64_t);
void clang_throw(int);
std::vector<std::string> exchange(std::vector<std::string>);
int clang_catch(Callback);
uint64_t core(uint64_t);
extern int main_destructions;
void destructor_callback();
