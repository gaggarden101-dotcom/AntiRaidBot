import os
import sys
import subprocess
from threading import Thread
from flask import Flask

# Function to run the bot.py script
def run_bot():
    # Use sys.executable to ensure the correct Python interpreter is used
    # This runs bot.py as a separate process, which is more robust than just import
    # IMPORTANT: If your bot file is named 'CryptoBot.py', change "bot.py" to "CryptoBot.py" here.
    subprocess.run([sys.executable, "bot.py"]) 

# Start the bot.py script in a separate thread
# This prevents the Flask web server from blocking your Discord bot's operations
bot_thread = Thread(target=run_bot)
bot_thread.start()

# This is a dummy Flask app that Render will detect and use to provide a public URL.
# Your Discord bot's logic runs independently in 'bot.py'.
app = Flask(__name__)

@app.route('/')
def home():
    return "Your Discord Bot's Web Server is Active!"

# Render expects the web service to listen on the port specified by the PORT environment variable.
# If not set, it defaults to 8080.
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)
