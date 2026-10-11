from app import create_app

app = create_app()

if __name__ == "__main__":
    debug = app.config["DEBUG"]
    # The debugger lets anyone who can reach the port run code, so debug mode
    # only listens on this machine.
    host = "127.0.0.1" if debug else "0.0.0.0"
    app.run(host=host, port=5000, debug=debug)
