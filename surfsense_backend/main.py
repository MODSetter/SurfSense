import uvicorn
import argparse

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Run the SurfSense application')
    parser.add_argument('--reload', action='store_true', help='Enable hot reloading')
    args = parser.parse_args()

    uvicorn.run(
        "app.app:app",
        host="0.0.0.0",
        log_level="info",
        reload=args.reload,
        reload_dirs=["app"]
    )
