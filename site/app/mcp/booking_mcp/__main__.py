import os

from booking_mcp.server import build_server


def main() -> None:
    server = build_server(os.environ.get("APP_API_URL", "http://localhost:8001"))
    if os.environ.get("MCP_TRANSPORT", "http").lower() == "stdio":
        server.run(transport="stdio")
    else:
        server.run(transport="http", host="0.0.0.0", port=int(os.environ.get("MCP_PORT", "8002")), path="/mcp")


if __name__ == "__main__":
    main()
