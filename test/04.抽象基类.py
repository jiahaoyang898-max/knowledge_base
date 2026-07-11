from abc import ABC, abstractmethod

class BaseWorker(ABC):
    def __call__(self,text:str):
        print("-----[日志]开始干活啦----")
        result = self.do_work(text)
        print("----[日志]干完收工啦------")
        return result
    @abstractmethod
    def do_work(self,text:str):
        pass
class UpperWorker(BaseWorker):
    def do_work(self,text:str):
        return text.upper()
class ReverseWorker(BaseWorker):
    def do_work(self,text:str):
        return text[::-1]
if __name__ == '__main__':
    #让大写员工干活
    worker_a = UpperWorker()
    print("结果:", worker_a("hello"))
    print("/n"+"="*30+"/n")
    #让倒序员工干活
    worker_b = ReverseWorker()
    print("结果：", worker_b("hello"))
