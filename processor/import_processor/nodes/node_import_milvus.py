import json
import logging
from typing import Dict, Any, List
from pymilvus import DataType
from config.milvus_config import milvus_config
from processor.import_processor.base import BaseNode, setup_logging
from processor.import_processor.exceptions import StateFieldError, MilvusError
from processor.import_processor.state import ImportGraphState
from utils.milvus_utils import get_milvus_client, escape_milvus_string

class NodeImportMilvus(BaseNode):
    name:str = "node_import_milvus"
    def process(self,state:ImportGraphState)->ImportGraphState:
        chunks_json_data,vector_dimension = self._step_1_check_input(state)
        client = self._step_2_prepare_collection(vector_dimension)
        self._step_3_clean_old_data(client,chunks_json_data)
        updatad_chunks =self._step_4_insert_data(client,chunks_json_data)
        state["chunks"] = updatad_chunks
        return state

    def _step_1_check_input(self,state:Dict[str,Any])-> tuple[List[Dict[str,Any]],int]:
        chunks = state.get("chunks")
        if not chunks:
            raise StateFieldError(field_name="chunks",message="chunks不能为空",expected_type = list)
        if not isinstance(chunks,list):
            raise StateFieldError(field_name="chunks",message="chunks数据类型不正确",expected_type = list)
        first_chunk = chunks[0]
        if 'dense_vector' not in first_chunk:
            raise StateFieldError(field_name="chunks",message="错误：数据中缺失dense_vector字段")
        if 'sparse_vector' not in first_chunk:
            raise StateFieldError(field_name="chunks",message="错误：数据中缺失sparse_vector字段")
        vector_dimension = len(first_chunk["dense_vector"])
        return chunks,vector_dimension

    def _step_2_prepare_collection(self,vector_dimension:int):
        milvus_client = get_milvus_client()
        if not milvus_client:
            self.logger.error("Milvus连接失败")
            raise MilvusError("Milvus连接失败")
        collections_name = milvus_config.chunks_collection
        if not milvus_client.has_collection(collections_name):
            self._create_chunks_collection(collections_name,milvus_client,vector_dimension)
        return milvus_client
    def _create_chunks_collection(self,collections_name,milvus_client,vector_dimension):
        schema = milvus_client.create_schema(auto_id=True,enable_dynamic_field = True)
        schema.add_field(
            field_name = "chunk_id",
            datatype = DataType.INT64,
            is_primary = True,
            auto_id = True
        )
        schema.add_field(
            field_name="content",
            datatype=DataType.VARCHAR,
            max_length = 65535
        )
        schema.add_field(
            field_name="title",
            datatype=DataType.VARCHAR,
            max_length = 100
        )
        schema.add_field(
            field_name="parent_title",
            datatype=DataType.VARCHAR,
            max_length = 100,
            default_value = ""
        )
        schema.add_field(
            field_name="part",
            datatype=DataType.INT8
        )
        schema.add_field(
            field_name="file_title",
            datatype=DataType.VARCHAR,
            max_length = 100
        )
        schema.add_field(
            field_name="item_name",
            datatype=DataType.VARCHAR,
            max_length = 100
        )
        schema.add_field(
            field_name="sparse_vector",
            datatype=DataType.SPARSE_FLOAT_VECTOR
        )
        schema.add_field(
            field_name="dense_vector",
            datatype=DataType.FLOAT_VECTOR,
            dim = vector_dimension
        )
        index_params = milvus_client.prepare_index_params()
        index_params.add_index(
            field_name="dense_vector",
            index_name = "dense_vector_index",
            index_type="AUTOINDEX",
            metric_type = "IP"
        )
        index_params.add_index(
            field_name="sparse_vector",
            index_name = "sparse_inverted_index",
            index_type="SPARSE_INVERTED_INDEX",
            metric_type = "IP",
            params = {
                "inverted_index_algo":"DAAT_MAXSCORE",
                "normalize":True,
                "quantization":"none"
            }
        )
        milvus_client.create_collection(
            collection_name=collections_name,
            schema=schema,
            index_params=index_params
        )

    def _step_3_clean_old_data(self,client,chunks_json_data):
        file_title = chunks_json_data[0].get("file_title")
        self._clear_chunks_by_file_title(client,file_title)
    def _clear_chunks_by_file_title(self,client,file_title):
        try:
            file_title = escape_milvus_string(file_title)  #对文件标题字符串做Milvus 特殊字符转义清洗
            client.delete(
                collection_name =milvus_config.chunks_collection,
                filter = f"file_title == '{file_title}'"
            )
        except Exception as e:
            self.logger.error(f"Milvus 数据删除失败：{str(e)}")
            raise MilvusError(f"Milvus 数据删除失败：{str(e)}")

    def _step_4_insert_data(self,client,chunks_json_data):
        for item in chunks_json_data:
            item["part"] = 0
        result =client.insert(
            collection_name=milvus_config.chunks_collection,
            data=chunks_json_data
        )
        inserted_id = result.get("ids")
        for idx,item in enumerate(chunks_json_data):
            item["chunk_id"] = inserted_id[idx]
        return chunks_json_data


if __name__ == "__main__":
    setup_logging()
    json_path = r"D:\output\hak180产品安全手册\state_vector.json"
    with open(json_path, "r", encoding="utf-8") as f:
        state_json = f.read()
    state = json.loads(state_json)
    init_state ={
        "chunks" : state.get("chunks")
    }
    node_import_milvus = NodeImportMilvus()
    result = node_import_milvus(init_state)
    logging.getLogger().info(json.dumps(result,ensure_ascii=False,indent=4))