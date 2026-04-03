import os

from project.backend.app import create_app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("BACKEND_PORT", os.environ.get("PORT", 8000)))
    uvicorn.run("project.backend.main:app", host="0.0.0.0", port=port, reload=True)
