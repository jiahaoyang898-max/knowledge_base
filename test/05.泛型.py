from typing import Any,TypeVar,List
T = TypeVar('T')
# 1. 使用 Any 的函数
def get_first_ant(items:List[Any])->Any:
    return items[0]
def get_first_generic(items:List[T])->T:
    return items[0]
if __name__ == '__main__':
    names = ["alice","bob"]
    res_any = get_first_ant(names)
    res_gen = get_first_generic(names)
    print(res_any)
    print(res_gen)
