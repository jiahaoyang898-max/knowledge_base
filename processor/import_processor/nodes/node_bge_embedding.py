import json
import logging
from typing import Dict, List

from processor.import_processor.base import BaseNode, setup_logging
from processor.import_processor.exceptions import StateFieldError
from processor.import_processor.state import ImportGraphState
from utils.embedding_utils import generate_embeddings

class NodeBGEEmbedding(BaseNode):
    name = "node_bge_embedding"
    def process(self,state: ImportGraphState)->ImportGraphState:
        chunks = self._step_1_validate_input(state)
        output_data = self._step_2_generate_embeddings(chunks)
        state["chunks"] = output_data
        return state

    def _step_1_validate_input(self,state:ImportGraphState)->List[Dict]:
        chunks = state.get("chunks")
        if not chunks:
            raise StateFieldError(field_name="chunks",message="chunks数据类型不正确",expected_type=list)
        return chunks
    def _step_2_generate_embeddings(self,chunks:List[Dict[str,str]]) -> List[Dict[str,str]]:
        batch_size = 3
        output_data = []
        for i in range(0,len(chunks),batch_size):
            batch_chunks = chunks[i:i+batch_size]
            texts = [f"{chunk['item_name']} \n{chunk['content']}" for chunk in batch_chunks]
            vectors = generate_embeddings(texts)
            dense_vectors = vectors.get("dense")
            sparse_vectors = vectors.get("sparse")
            for j,text in enumerate(texts):
                chunk =  batch_chunks[j]
                chunk["dense_vector"] = dense_vectors[j]
                chunk["sparse_vector"] = sparse_vectors[j]
                output_data.append(chunk)
        return output_data


if __name__ == '__main__':
    setup_logging()
    json_path = r"D:\output\hak180产品安全手册\state.json"
    with open(json_path,"r",encoding="utf-8") as f:
        state_json = f.read()
    state = json.loads(state_json)
    init_state = {
        "chunks":state.get("chunks")
    }
    node_bge_embedding = NodeBGEEmbedding()
    result = node_bge_embedding(init_state)
    vector_json_path = "D:\output\hak180产品安全手册\state_vector.json"
    with open(vector_json_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=4)
    logging.getLogger().info(f"💾 混合向量化成功！包含 dense/sparse 向量的数据已写入: {vector_json_path}")
    logging.getLogger().info(json.dumps(result,ensure_ascii=False,indent=4))