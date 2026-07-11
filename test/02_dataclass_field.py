from dataclasses import dataclass,field

@dataclass
class User:
    username: str
    age: int = 18
    tags : list = field(default_factory=list)
#开始测试
print("------测试1：只提供必须字段-------")
user1 = User("Alice")
print(f"user1:{user1}")
print("\n----测试2：提供所有字段--------")
user2 = User("Bob",25,["developer","pythonist"])
print(f"user2:{user2}")
print("\n-----测试3：验证可变默认值的独立性---")
user3 = User("Charlie")
user4 = User("David")
user3.tags.append("new_tag")
print(f"user3.tags:{user3.tags}")
print(f"user4.tags:{user4.tags}")

# #单例设计模式
from dataclasses import dataclass,field
from typing import Optional
import datetime

@dataclass
class SimpleLogger:
    """日志记录器类"""
    log_level : str = "INFO"
    init_time: str = field(
        default_factory= lambda : datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    )
    def log(self,message: str):
        print(f"[{self.init_time}][{self.log_level}] {message}]")
_logger_instance : Optional[SimpleLogger] = None
def get_logger() -> SimpleLogger:
    global _logger_instance
    if _logger_instance is None:
        _logger_instance = SimpleLogger()
    return _logger_instance
if __name__ == "__main__":
    print("------第一次获取Logger------")
    logger1 = get_logger()
    logger1.log("这是第一条日志")
    import time
    time.sleep(1)
    print("\n------第二次获取Logger------")
    logger2 = get_logger()
    logger2.log("这是第二条日志")
    print("\n------验证唯一性------")
    is_same = logger1 is logger2
    print(f"logger1和logger2是同一个实例吗？{is_same}")















