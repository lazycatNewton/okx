"""okx-backend 包入口。"""


def main() -> None:
    import uvicorn

    uvicorn.run("okx_backend.main:app", host="0.0.0.0", port=8000, reload=False)
