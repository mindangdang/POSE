from project.backend.basic_functions.utils import _extract_text_vector_sync, _extract_vector_sync
import numpy as np
import asyncio

async def test_function(image_url:str, detail:str):

    def cosine_similarity(vec1, vec2):
            if vec1 is None or vec2 is None:
                return 0.0
            vec1 = np.array(vec1).flatten()
            vec2 = np.array(vec2).flatten()
            
            norm1 = np.linalg.norm(vec1)
            norm2 = np.linalg.norm(vec2)
            if norm1 == 0 or norm2 == 0:
                return 0.0
                
            return np.dot(vec1, vec2) / (norm1 * norm2)
    
    image_vector = np.array(await _extract_vector_sync(image_url))
    text_vector = np.array(await _extract_text_vector_sync(detail))

    return cosine_similarity(image_vector,text_vector)


if __name__ == "__main__":
    image_url = 'https://image.production.fruitsfamily.com/public/product/resized%40width1125/4WGBb5AMhS-363a5e670160.jpg'
    detail = 'animal'
    value = asyncio.run(test_function(image_url, detail))
    print(value)

#python -m project.backend.tests.test