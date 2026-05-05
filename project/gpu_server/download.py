from huggingface_hub import snapshot_download

# 모델을 저장할 로컬 경로 지정
LOCAL_MODEL_PATH = "project/gpu_server/models/marqo-fashionSigLIP"

# 최초 1회 실행하여 모델 파일 전체를 다운로드
snapshot_download(
    repo_id="Marqo/marqo-fashionSigLIP",
    local_dir=LOCAL_MODEL_PATH,
    local_dir_use_symlinks=False  # 실제 파일로 저장 (도커 환경 등에서 유리)
)