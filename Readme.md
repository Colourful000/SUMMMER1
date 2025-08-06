Food Assistant - An AI-Powered Nutrition Analysis App



Author: Yicheng Xiang



Institution: University of Bristol

📖 Overview



Food Assistant is a comprehensive web application designed to be your personal nutrition companion. Leveraging a suite of powerful AI models, this application allows users to track their meals, understand their nutritional intake, and receive personalized advice. You can analyze your food by simply uploading a picture, taking a photo with your phone, or even just by speaking its name.



The application is built with a mobile-first approach and can be "installed" on your phone's home screen as a Progressive Web App (PWA) for a native-like experience.

✨ Key Features



This project integrates multiple cutting-edge technologies to deliver a seamless user experience:



&nbsp;   Multi-Modal Food Input:



&nbsp;       📷 Image Upload: Analyze a food item by uploading an existing picture.



&nbsp;       📸 Camera Capture: Use your phone's camera directly within the app to take a photo for analysis.



&nbsp;       🎤 Voice Input: Simply press a button, say the name of the food, and let the app do the rest.



&nbsp;   Advanced AI Analysis Pipeline:



&nbsp;       Food Recognition: Utilizes a YOLOv8 model to accurately identify food items in an image.



&nbsp;       Weight Estimation: Employs Google's Gemini 1.5 Pro vision model to intelligently estimate the weight of the food in grams based on visual cues.



&nbsp;       Nutrition Advice: Uses the DeepSeek language model to provide personalized, conversational nutrition advice based on the food's nutrients and the user's personal profile.



&nbsp;       Speech-to-Text: Powered by OpenAI's Whisper to accurately transcribe spoken food names.



&nbsp;   Personalized User Experience:



&nbsp;       User Authentication: Secure registration and login system.



&nbsp;       User Profiles: Users can save personal data like gender, age, height, weight, and dietary goals to receive more tailored advice.



&nbsp;       Nutrition History: All analyses can be saved to a personal history log for tracking over time.



&nbsp;       AI Dietician: A dedicated feature that analyzes your eating habits over a selected date range and provides a holistic summary and advice.



&nbsp;   Modern Web Technology:



&nbsp;       Progressive Web App (PWA): Can be added to your mobile home screen, providing a full-screen, app-like experience with a custom icon.



&nbsp;       Responsive Design: The UI is optimized for a seamless experience on both desktop and mobile devices.



&nbsp;       Interactive UI: Features like loading animations provide clear feedback to the user during AI analysis.



🛠️ Tech Stack



&nbsp;   Backend: Python, Flask, SQLAlchemy



&nbsp;   Database: SQLite



&nbsp;   Frontend: HTML, CSS, JavaScript



&nbsp;   AI Models:



&nbsp;       ultralytics/yolov8



&nbsp;       google-generativeai (Gemini 1.5 Pro)



&nbsp;       deepseek-api



&nbsp;       openai-whisper



&nbsp;   Deployment/Tunneling: Tested with localtunnel and ngrok.



🚀 How to Run Locally



To get this project running on your own machine, please follow these steps.

1\. Prerequisites



&nbsp;   Python 3.9 or higher



&nbsp;   An environment with GPU support (for torch) is recommended for best performance, but the code will fall back to CPU if not available.



&nbsp;   API keys for:



&nbsp;       Google AI (for Gemini)



&nbsp;       DeepSeek



2\. Installation



\# 1. Clone the repository to your local machine

git clone https://github.com/Colourful000/SUMMMER1.git

cd food-recognition



\# 2. It is highly recommended to create a virtual environment

python -m venv .venv

source .venv/bin/activate  # On Windows, use `.venv\\Scripts\\activate`



\# 3. Install all the required dependencies

pip install -r requirements.txt



3\. Configuration



You need to provide your API keys to the application. The recommended way is to set them as environment variables.



On Windows (PowerShell):



$env:GOOGLE\_API\_KEY="YOUR\_GOOGLE\_API\_KEY"

$env:DEEPSEEK\_API\_KEY="YOUR\_DEEPSEEK\_API\_KEY"



On macOS/Linux:



export GOOGLE\_API\_KEY="YOUR\_GOOGLE\_API\_KEY"

export DEEPSEEK\_API\_KEY="YOUR\_DEEPSEEK\_API\_KEY"



Remember to replace YOUR\_...\_KEY with your actual keys.

4\. Initialize the Database



Before running the app for the first time, you need to create the database file and its tables.



python init\_db.py



This will create an app.db file in your project directory.

5\. Run the Application



You are now ready to launch the app!



python app.py



The application will be running on http://127.0.0.1:5000. Open this address in your web browser.

6\. Mobile Testing (Optional)



To test the mobile features like camera capture and the PWA installation, you can use a tunneling service like localtunnel.



\# In a new terminal, run:

lt --port 5000 --subdomain your-unique-name



This will give you a public URL that you can open on your phone.

