#include "shared.h"
#include <iostream>
#include <chrono>
#include <cstring>
int main_destructions=0;
void destructor_callback(){++main_destructions;}
static uint64_t callback(uint64_t x){return x*7+13;}
static uint64_t throws(uint64_t){throw std::runtime_error("msvc");}
static uint64_t reference(uint64_t x){for(unsigned i=0;i<128;++i){x^=x>>17;x*=0xed5ad4bbU;x^=x>>11;x*=0xac4c1b51U;x^=x>>15;}return x;}
int main(int argc,char** argv){
  if(argc>1&&std::strcmp(argv[1],"--timing")==0){
    uint64_t x=17;const unsigned rounds=100000;
    auto start=std::chrono::steady_clock::now();
    for(unsigned i=0;i<rounds;++i)x=core(x+i);
    auto stop=std::chrono::steady_clock::now();
    std::cout<<"{\"ns_per_call\":"<<double(std::chrono::duration_cast<std::chrono::nanoseconds>(stop-start).count())/rounds<<",\"checksum\":"<<x<<"}\n";return 0;
  }
  for(uint64_t x=0;x<10000;++x)if(core(x)!=reference(x))return 1;
  Base* b=make_object(49);auto* d=dynamic_cast<Derived*>(b);auto* side=dynamic_cast<Side*>(b);
  if(!d||!side||side->marker()!=71||d->value(123)!=(reference(123)^49))return 2;
  delete b; // MSVC generated delete dispatches a Clang destructor.
  delete_object(new Derived(7)); // Clang delete consumes a MSVC allocation.
  if(via_callback(callback,17)!=(callback(17)^reference(17)))return 3;
  if(Box<unsigned>{19}.twice()!=38||exchange_box(Box<uint64_t>{19}).value!=38)return 4;
  auto v=exchange({"msvc",std::string(200,'a')});if(v.size()!=3||v[2]!="clang")return 5;
  bool caught=false;try{clang_throw(1);}catch(const std::runtime_error& e){caught=std::string(e.what())=="cross-module";}
  if(!caught||main_destructions!=1||clang_catch(throws)!=91)return 6;
  std::cout<<"WUXIANG_ABI_OK\n";
}
