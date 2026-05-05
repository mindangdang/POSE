from huggingface_hub import snapshot_download

# 모델을 저장할 로컬 경로 지정
LOCAL_MODEL_PATH = "project/gpu_server/models/marqo-fashionSigLIP"

# 최초 실행 시 모델을 Hugging Face Hub에서 다운로드하여 로컬에 저장 or 그냥 실행해서 캐시되게 하기
snapshot_download(
    repo_id="Marqo/marqo-fashionSigLIP",
    local_dir=LOCAL_MODEL_PATH,
    local_dir_use_symlinks=False  # 실제 파일로 저장 (도커 환경 등에서 유리)
)