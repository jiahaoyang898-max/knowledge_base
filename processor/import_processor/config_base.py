from dataclasses import dataclass,field
from typing import Set,Optional
import os
from dotenv import load_dotenv
load_dotenv(override=True)

@dataclass
class ImportConfig:
    """导入流程配置"""
    #文档处理配置
    max_content_length:int = 2000
    img_content_length:int = 200
    min_content_length:int = 500
    overlap_sentences : int = 10
    item_name_chunk_k :int = 3
    item_name_chunk_size :int = 2500
    # 支持的图片扩展名
    image_extensions : Set[str] = field(
        default_factory=lambda : {
            ".jpg", ".jpeg", ".png", ".gif",".bmp",".webp"
        }
    )
    # ==================== MinerU 配置 ====================
    mineru_api_token: str = field(
        default_factory=lambda: os.getenv("MINERU_API_TOKEN", "")
    )
    mineru_base_url: str = field(
        default_factory=lambda: os.getenv("MINERU_BASE_URL", "")
    )
    #LLM配置
    openai_api_base : str =field(
        default_factory=lambda : os.getenv("OPENAI_API_URL")
    )
    openai_api_key : str =field(
        default_factory=lambda : os.getenv("OPENAI_API_KEY")
    )
    vl_madel : str =field(
        default_factory=lambda : os.getenv("VL_MADE","")
    )
    item_modelc : str =field(
        default_factory=lambda : os.getenv("ITEM_MODEL_C","")
    )
    default_model :str = field(
        default_factory=lambda : os.getenv("MODEL","")
    )
    #Milvus配置
    milvus_url : str =field(
        default_factory=lambda : os.getenv("MILVUS_URL","")
    )
    chunks_collection : str =field(
        default_factory=lambda : os.getenv("CHUNKS_COLLECTION","")
    )
    item_name_collection : str =field(
        default_factory=lambda : os.getenv("ITEM_NAME_COLLECTION","")
    )
    #MinIo配置
    minio_endpoint : str =field(
        default_factory=lambda : os.getenv("MINIO_ENDPOINT","")
    )
    minio_access_key : str =field(
        default_factory=lambda : os.getenv("MINIO_ACCESS_KEY","")
    )
    minio_secret_key : str =field(
        default_factory=lambda : os.getenv("MINIO_SECRET_KEY","")
    )
    minio_bucket : str =field(
        default_factory=lambda : os.getenv("MINIO_BUCKET_NAME","")
    )
    minio_secure : bool = False
    #向量配置
    embedding_dim : int = field(
        default_factory=lambda : os.getenv("EMBEDDING_DIM","1024")
    )
    embedding_batch_size : int = 8
    #速率限制
    requests_per_minute : int = 15
    @classmethod
    def from_env(cls) -> "ImportConfig":
        """从环境变量加载配置"""
        return cls()
    def get_minio_base_url(self) -> str:
        """获取MinIo基础URL"""
        protocol = "https://"if self.minio_secure else "http://"
        return protocol + f"{self.minio_endpoint}"

#全局单例
_config : Optional[ImportConfig] = None
def get_config() -> ImportConfig:
    """获取配置单例"""
    global _config
    if _config is None:
        _config = ImportConfig.from_env()
    return _config

