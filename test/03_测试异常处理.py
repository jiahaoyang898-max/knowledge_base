from processor.import_processor.exceptions import  ValidationError
class MilvusError(Exception):
    def __init__(self, message:str,node_name :str =None,cause:Exception = None):
        self.message = message
        self.node_name = node_name
        self.cause = cause
        super().__init__(self._build_msg())
    def _build_msg(self):
        if self.node_name and self.cause:
            return f"[{self.node_name}]{self.message}(原因：{repr(self.cause)})"
        return f"[{self.node_name}]{self.message}"if self.node_name else self.message
class ValidationError(MilvusError):
    pass

try:
    raise ValidationError("数据类型不匹配")
except ValidationError as e:
    raise ValidationError(
        message="向量写入失败",
        node_name = "import_milvus",
        cause = e
    )
