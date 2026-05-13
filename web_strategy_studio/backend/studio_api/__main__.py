"""CLI: python -m studio_api"""

import uvicorn

from studio_api.config import settings


def main() -> None:
    uvicorn.run(
        "studio_api.app:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=False,
    )


if __name__ == "__main__":
    main()
