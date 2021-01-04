from app import app
from system_manager.Supervise import Supervise

supervisor = Supervise()
app.config["supervisor"] = supervisor

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=3636)
