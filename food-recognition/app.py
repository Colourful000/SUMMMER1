import os
import threading
import argparse
import getpass
from openai import OpenAI
from flask_cors import CORS
from pyngrok import ngrok, conf
from backend.routes import set_routes
from backend.constants import UPLOAD_FOLDER, CSV_FOLDER, DETECTION_FOLDER, SEGMENTATION_FOLDER, METADATA_FOLDER
from backend.models import db, User
from werkzeug.security import generate_password_hash, check_password_hash
from backend.models import AnalysisHistory
from flask import Flask, render_template, request, redirect, url_for, flash, session,jsonify, redirect, url_for,send_from_directory
from datetime import datetime, timedelta
from backend.routes import build_prompt
from openai import OpenAI
from backend.utils import *
import whisper
import json
import pandas as pd
import google.generativeai as genai
from PIL import Image, ExifTags

NUTRITION_DF = pd.read_csv('nutrition_db.csv')


def create_app():
    app = Flask(__name__, template_folder='templates', static_folder='static')
    app.config['SECRET_KEY'] = 'sk-58530a01a7a94d66a92c010a8a86f0a9'  # 换成你自己的
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///C:/Users/GM7/PycharmProjects/SummerProject/food-recognition/app.db'
    db.init_app(app)

    CORS(app, resources={r"/api/*": {"origins": "*"}})
    app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
    app.config['CSV_FOLDER'] = CSV_FOLDER
    app.config['DETECTION_FOLDER'] = DETECTION_FOLDER
    app.config['SEGMENTATION_FOLDER'] = SEGMENTATION_FOLDER

    set_routes(app)


    # --- 安全地配置API密钥 ---
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("错误：请先设置 GOOGLE_API_KEY 环境变量！")
    genai.configure(api_key=api_key)

    client = OpenAI(
        api_key=os.getenv("DEEPSEEK_API_KEY") or "sk-58530a01a7a94d66a92c010a8a86f0a9",
        base_url="https://api.deepseek.com"
    )

    def estimate_weight_with_gemini(image_path: str):
        """
        【英文版】使用Gemini API来估算图片中食物的重量。
        这个版本会用英文进行推理。
        """
        model = genai.GenerativeModel('gemini-1.5-pro-latest')
        prompt = """
        You are a top-tier nutritionist skilled in visual weight estimation.
        Please analyze the image I provide and estimate the weight of the main food item in grams.

        Your thinking process should be as follows:
        1. Identify the main food item in the image.
        2. Look for common reference objects in the image (e.g., fork, spoon, plate, hand, cup).
        3. If you find a reference object, state what it is and its standard size (e.g., a standard dinner fork is about 19 cm long).
        4. Based on the reference object, estimate the food's dimensions and volume.
        5. Combining the food type and its typical density, calculate the final weight.
        6. If you cannot find any reference objects, provide a reasonable average weight based on the food type and common portion sizes.

        Finally, please return your analysis strictly in the following JSON format, without any extra explanatory text or markdown like "```json" or "```":
        {
          "food_name": "Name of the food",
          "estimated_weight_g": your estimated weight value (return numbers only),
          "reasoning": "Your brief reasoning process (e.g., 'Estimated using a fork as a reference.')"
        }
        """
        try:
            print("--- 开始调用Gemini API ---")
            img = Image.open(image_path)

            response = model.generate_content([prompt, img])

            print("\n--- 已收到Gemini的原始回复 (下方是完整内容) ---")
            print(response.text)
            print("--- 原始回复结束 ---\n")

            cleaned_text = response.text.strip()
            if cleaned_text.startswith("```json"):
                cleaned_text = cleaned_text[7:]
            if cleaned_text.endswith("```"):
                cleaned_text = cleaned_text[:-3]

            print("--- 正在尝试解析清理后的文本 ---")
            result_json = json.loads(cleaned_text)
            print("--- JSON解析成功！ ---")
            return result_json

        except Exception as e:
            print(f"\n--- 处理过程中发生错误 ---")
            print(f"错误类型: {type(e).__name__}")
            print(f"错误信息: {e}")
            print("------------------------\n")
            return None
    @app.route('/svg_static/<path:filename>')
    def svg_static(filename):
        if filename.endswith('.svg'):
            return send_from_directory('static/assets/login', filename, mimetype='image/svg+xml')
        return send_from_directory('static/assets/login', filename)
    # -------- 用户登录 --------
    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if request.method == 'POST':
            username = request.form['username']
            password = request.form['password']
            user = User.query.filter_by(username=username).first()
            if user and check_password_hash(user.password, password):
                session['user_id'] = user.id
                session['username'] = user.username
                flash('Login successful!', 'success')
                return redirect(url_for('dashboard'))
            else:
                flash('Invalid username or password', 'danger')
                return redirect(url_for('login'))
        return render_template('login.html', show_register=False)


    # -------- 用户主页 dashboard --------
    @app.route('/dashboard')
    def dashboard():
        if 'user_id' not in session:
            flash('Please log in first!')
            return redirect(url_for('login'))
        # --- 关键修复：使用现代的 db.session.get() 方法 ---
        user = db.session.get(User, session['user_id'])
        return render_template('dashboard.html', username=session.get('username'), user=user)

    # -------- 用户注册 --------
    @app.route('/register', methods=['GET', 'POST'])
    def register():
        if request.method == 'POST':
            username = request.form['username']
            password = request.form['password']
            gender = request.form.get('gender')
            age = request.form.get('age')
            height = request.form.get('height')
            weight = request.form.get('weight')
            if User.query.filter_by(username=username).first():
                flash('Username already exists', 'danger')
                return redirect(url_for('register'))
            hashed_password = generate_password_hash(password)
            new_user = User(
                username=username,
                password=hashed_password,
                gender=gender,
                age=int(age) if age else None,
                height=float(height) if height else None,
                weight=float(weight) if weight else None
            )
            db.session.add(new_user)
            db.session.commit()
            session['user_id'] = new_user.id
            session['username'] = new_user.username
            flash('Registration successful! You are now logged in.', 'success')
            return redirect(url_for('dashboard'))
        return render_template('login.html', show_register=True)

    @app.route('/logout')
    def logout():
        session.clear()
        flash('You have been logged out.')
        return redirect(url_for('login'))

    @app.route('/upload', methods=['GET', 'POST'])
    def upload_food():
        if request.method == 'POST':
            file = request.files.get('file')
            if not file:
                flash('No file uploaded')
                return redirect(url_for('upload_food'))

            filename, filepath, filetype = process_upload_file(request)

            try:
                image = Image.open(filepath)
                orientation_tag = next((tag for tag, name in ExifTags.TAGS.items() if name == 'Orientation'), None)
                if orientation_tag and hasattr(image, '_getexif') and image._getexif() is not None:
                    exif = dict(image._getexif().items())
                    if exif.get(orientation_tag) == 3:
                        image = image.rotate(180, expand=True)
                    elif exif.get(orientation_tag) == 6:
                        image = image.rotate(270, expand=True)
                    elif exif.get(orientation_tag) == 8:
                        image = image.rotate(90, expand=True)
                image.save(filepath)
                print(f"Image orientation corrected and saved to {filepath}")
            except Exception as e:
                print(f"Could not process EXIF orientation tag for {filepath}: {e}")
                pass

            out_name, output_path, output_type, result_dict = process_image_file(
                filename, filepath, "yolov8s", False, False, 0.15, 0.5, False, False
            )

            if result_dict and 'names' in result_dict and result_dict['names']:
                food_name = result_dict['names'][0]
                nutrients = {}
                idx = 0
                for k in ['calories', 'protein', 'fat', 'carbs', 'fiber']:
                    nutrients[k] = result_dict.get(k, [None])[idx]
                if all(v is None for v in nutrients.values()):
                    nutrients = get_nutrient_from_db(food_name)
            else:
                food_name = "Unknown"
                nutrients = {k: None for k in ['calories', 'protein', 'fat', 'carbs', 'fiber']}

            gemini_result = estimate_weight_with_gemini(filepath)
            if gemini_result:
                estimated_weight = int(gemini_result.get('estimated_weight_g', 200))
                estimation_method = gemini_result.get('reasoning', 'AI estimation')
            else:
                estimated_weight = 200
                estimation_method = "Weight estimation by Gemini failed, used default."

            final_nutrients = nutrients
            if all(v is not None for v in nutrients.values()):
                scaling_factor = estimated_weight / 100.0
                final_nutrients = {k: round(v * scaling_factor, 2) for k, v in nutrients.items()}

            user_info = {}
            meal_type = request.form.get('tag')
            if 'user_id' in session:
                # --- 关键修复：使用现代的 db.session.get() 方法 ---
                user = db.session.get(User, session['user_id'])
                if user:
                    user_info = {
                        "gender": user.gender, "age": user.age, "height": user.height,
                        "weight": user.weight, "diet_goal": user.diet_goal,
                        "special_diet": user.special_diet, "activity_level": user.activity_level
                    }

            data_for_advice = {
                "food": food_name, "nutrients": final_nutrients, "user_info": user_info,
                "meal_type": meal_type, "estimated_weight": estimated_weight,
                "estimation_method": estimation_method
            }

            system_prompt = (
                "You are a board-certified nutritionist. Your job is to provide personalized, professional nutrition analysis for the user. "
                "When responding, you must use only full, natural sentences and never use any bullet points, numbers, dashes, asterisks, or any other formatting symbols. "
                "Do not use bold, italics, code blocks, or markdown. Your answer should always be a single, flowing paragraph, not separated into sections or lists. "
                "Never use rhetorical or leading questions. Just give a direct, friendly, and informative nutrition analysis, as if you are talking to the user face to face. "
                "Your response should be highly relevant, concise, and about 60 words."
            )

            prompt_for_advice = build_prompt(data_for_advice)
            ai_advice = ""
            try:
                response = client.chat.completions.create(
                    model="deepseek-chat",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt_for_advice}
                    ],
                    stream=False
                )
                ai_advice = response.choices[0].message.content
            except Exception as e:
                ai_advice = f"AI analysis failed: {e}"

            save_history = request.form.get('save_history') == 'true'
            if save_history and 'user_id' in session:
                tag = request.form.get('tag')
                history = AnalysisHistory(
                    user_id=session['user_id'],
                    food_name=food_name,
                    nutrients=json.dumps(final_nutrients),
                    ai_advice=ai_advice,
                    tag=tag
                )
                db.session.add(history)
                db.session.commit()

            return render_template(
                'analyze_result.html',
                food_name=food_name,
                nutrients=final_nutrients,
                ai_advice=ai_advice,
                estimated_weight=estimated_weight,
                estimation_method=estimation_method
            )

        return render_template('upload_file.html')

    @app.route('/history')
    def history():
        if 'user_id' not in session:
            flash('Please log in first!')
            return redirect(url_for('login'))

        records = AnalysisHistory.query.filter_by(user_id=session['user_id']).order_by(
            AnalysisHistory.timestamp.desc()).all()
        for r in records:
            try:
                r.nutrients_dict = json.loads(r.nutrients)
            except Exception:
                r.nutrients_dict = {}
        return render_template('history.html', records=records)

    @app.route('/delete_history/<int:history_id>', methods=['POST'])
    def delete_history(history_id):
        if 'user_id' not in session:
            flash('Please log in first!')
            return redirect(url_for('login'))
        record = AnalysisHistory.query.filter_by(id=history_id, user_id=session['user_id']).first()
        if record:
            db.session.delete(record)
            db.session.commit()
            flash('Record deleted successfully!')
        else:
            flash('Record not found or no permission to delete.')
        return redirect(url_for('history'))

    model = whisper.load_model("base")

    @app.route('/speech_to_text', methods=['POST'])
    def speech_to_text():
        if not os.path.exists('./tmp'):
            os.makedirs('./tmp')
        audio_file = request.files['audio']
        audio_path = f"./tmp/{audio_file.filename}"
        audio_file.save(audio_path)
        result = model.transcribe(audio_path, language='en')
        os.remove(audio_path)
        return jsonify({'text': result['text']})

    @app.route('/voice_input', methods=['GET', 'POST'])
    def voice_input():
        if 'user_id' not in session:
            flash('Please log in first!')
            return redirect(url_for('login'))

        if request.method == 'POST':
            food_text = request.form.get('food_text', '').strip()
            save_history = request.form.get('save_history') == 'true'
            tag = request.form.get('tag', None)
            estimated_weight = request.form.get('weight_input')

            try:
                estimated_weight = int(estimated_weight) if estimated_weight else 200
            except Exception:
                estimated_weight = 200

            nutrients = {k: None for k in ['calories', 'protein', 'fat', 'carbs', 'fiber']}
            try:
                result = NUTRITION_DF[NUTRITION_DF['name'].str.lower().str.contains(food_text.lower())]
                if not result.empty:
                    row = result.iloc[0]
                    nutrients = {
                        'calories': float(row['calories']), 'protein': float(row['protein']),
                        'fat': float(row['fat']), 'carbs': float(row['carbs']),
                        'fiber': float(row['fiber']),
                    }
            except Exception as e:
                print('CSV 查找异常:', e)

            final_nutrients = nutrients.copy()
            if all(v is not None for v in nutrients.values()):
                scaling_factor = estimated_weight / 100.0
                final_nutrients = {k: round(v * scaling_factor, 2) for k, v in nutrients.items()}

            user_info = {}
            meal_type = tag
            if 'user_id' in session:
                # --- 关键修复：使用现代的 db.session.get() 方法 ---
                user = db.session.get(User, session['user_id'])
                if user:
                    user_info = {
                        "gender": user.gender, "age": user.age, "height": user.height,
                        "weight": user.weight, "diet_goal": user.diet_goal,
                        "special_diet": user.special_diet, "activity_level": user.activity_level
                    }

            data = {
                "food": food_text, "nutrients": final_nutrients, "user_info": user_info,
                "meal_type": meal_type, "estimated_weight": estimated_weight,
                "estimation_method": "Manual input or default"
            }
            system_prompt = (
                "You are a board-certified nutritionist. Your job is to provide personalized, professional nutrition analysis for the user. "
                "When responding, you must use only full, natural sentences and never use any bullet points, numbers, dashes, asterisks, or any other formatting symbols. "
                "Do not use bold, italics, code blocks, or markdown. Your answer should always be a single, flowing paragraph, not separated into sections or lists. "
                "Never use rhetorical or leading questions. Just give a direct, friendly, and informative nutrition analysis, as if you are talking to the user face to face. "
                "Your response should be highly relevant, concise, and about 60 words."
            )
            prompt = build_prompt(data)
            ai_advice = ""
            try:
                response = client.chat.completions.create(
                    model="deepseek-chat",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt}
                    ],
                    stream=False
                )
                ai_advice = response.choices[0].message.content
            except Exception as e:
                ai_advice = f"AI analysis failed: {e}"

            if save_history and 'user_id' in session:
                history = AnalysisHistory(
                    user_id=session['user_id'],
                    food_name=food_text,
                    nutrients=json.dumps(final_nutrients),
                    ai_advice=ai_advice,
                    tag=tag
                )
                db.session.add(history)
                db.session.commit()

            return render_template(
                'analyze_result.html',
                food_name=food_text,
                nutrients=final_nutrients,
                ai_advice=ai_advice,
                estimated_weight=estimated_weight,
                estimation_method="Manual input or default"
            )
        return render_template('voice_input.html')

    @app.route('/camera_upload', methods=['GET'])
    def camera_upload():
        if 'user_id' not in session:
            flash('Please log in first!')
            return redirect(url_for('login'))
        return render_template('camera_upload.html')

    @app.route('/')
    def index():
        print("=== Root / visited, should redirect to /login ===")
        return redirect(url_for('login'))

    @app.route('/profile', methods=['GET', 'POST'])
    def profile():
        if 'user_id' not in session:
            flash('Please log in first!')
            return redirect(url_for('login'))
        # --- 关键修复：使用现代的 db.session.get() 方法 ---
        user = db.session.get(User, session['user_id'])
        if request.method == 'POST':
            user.gender = request.form.get('gender')
            user.age = request.form.get('age')
            user.height = request.form.get('height')
            user.weight = request.form.get('weight')
            user.diet_goal = request.form.get('diet_goal')
            user.special_diet = request.form.get('special_diet')
            user.activity_level = request.form.get('activity_level')
            db.session.commit()
            flash('Profile updated successfully!', 'success')
            return redirect(url_for('dashboard'))
        return render_template('profile.html', user=user)

    @app.route('/dietician_select', methods=['GET'])
    def dietician_select():
        if 'user_id' not in session:
            flash('Please log in first!')
            return redirect(url_for('login'))
        return render_template('dietician_select.html')

    @app.route('/dietician_result', methods=['GET', 'POST'])
    def dietician_result():
        if 'user_id' not in session:
            flash('Please log in first!')
            return redirect(url_for('login'))

        start_date = request.form.get('start_date') or request.args.get('start_date')
        end_date = request.form.get('end_date') or request.args.get('end_date')
        user_message = request.form.get('user_message', '').strip() if request.method == 'POST' else ''

        try:
            start = datetime.strptime(start_date, "%Y-%m-%d")
            end = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
        except (ValueError, TypeError):
            flash('Invalid date.')
            return redirect(url_for('dietician_select'))

        history = AnalysisHistory.query.filter(
            AnalysisHistory.user_id == session['user_id'],
            AnalysisHistory.timestamp >= start,
            AnalysisHistory.timestamp < end
        ).order_by(AnalysisHistory.timestamp.asc()).all()

        history_summaries = []
        for record in history:
            try:
                nutrients = json.loads(record.nutrients)
            except Exception:
                nutrients = {}
            history_summaries.append({
                "food": record.food_name, "nutrients": nutrients,
                "tag": record.tag, "ai_advice": record.ai_advice
            })

        base_context = "Here are the user's nutrition records for the selected dates:\n"
        for h in history_summaries:
            base_context += f"Food: {h['food']}, Tag: {h['tag']}, Nutrients: {h['nutrients']}, Previous AI Advice: {h['ai_advice']}\n"

        system_prompt = (
            "You are a warm, conversational, board-certified dietician. "
            "When you answer, you must only provide nutrition advice, never discuss anything else. "
            "You always consider the user's historical nutrition records provided below when answering. "
            "Never use any lists, bullets, or special formatting. Speak in a friendly, conversational tone. "
            "Never use dashes, hyphens, quotes, or any kind of list or numbered format. "
            "Respond only with full sentences, like you’re chatting face to face. "
            "Summarize what stands out, what concerns you, and what to change, but speak in a natural, supportive, flowing paragraph. "
            "Maximum 80 words."
        )

        ai_summary = ""
        ai_reply = None

        if request.method == 'GET' or not user_message:
            if history_summaries:
                summary_prompt = (base_context + "Please review these records and give the user a natural, spoken-style summary...")
                try:
                    response = client.chat.completions.create(
                        model="deepseek-reasoner",
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": summary_prompt}
                        ]
                    )
                    ai_summary = response.choices[0].message.content
                except Exception as e:
                    ai_summary = f"AI summary failed: {e}"
            else:
                ai_summary = "No nutrition history found for the selected date range."
            return render_template(
                'dietician_result.html', summary=ai_summary,
                start_date=start_date, end_date=end_date,
                user_message=None, ai_reply=None
            )
        else:
            chat_prompt = (base_context + f"\nUser's question: {user_message}\n" + "Please answer only as a nutritionist...")
            try:
                response = client.chat.completions.create(
                    model="deepseek-reasoner",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": chat_prompt}
                    ]
                )
                ai_reply = response.choices[0].message.content
            except Exception as e:
                ai_reply = f"AI reply failed: {e}"

            return render_template(
                'dietician_result.html', summary=None,
                start_date=start_date, end_date=end_date,
                user_message=user_message, ai_reply=ai_reply
            )

    return app


def get_nutrient_from_db(food_name):
    import pandas as pd
    df = pd.read_csv('nutrition_db.csv')
    result = df[df['name'].str.lower().str.contains(food_name.lower())]
    if not result.empty:
        row = result.iloc[0]
        return {
            'calories': float(row['calories']), 'protein': float(row['protein']),
            'fat': float(row['fat']), 'carbs': float(row['carbs']),
            'fiber': float(row['fiber']),
        }
    return {k: None for k in ['calories', 'protein', 'fat', 'carbs', 'fiber']}

# --- 主程序入口 ---
if __name__ == '__main__':
    parser = argparse.ArgumentParser('Online Food Recognition')
    parser.add_argument('--ngrok', action='store_true', default=False, help="Run on local or ngrok")
    parser.add_argument('--host', type=str, default='localhost', help="Local IP")
    parser.add_argument('--port', type=int, default=5000, help="Local port")
    parser.add_argument('--debug', action='store_true', default=False, help="Run app in debug mode")
    args = parser.parse_args()

    app = create_app()

    if __name__ == '__main__':
        parser = argparse.ArgumentParser('Online Food Recognition')
        parser.add_argument('--ngrok', action='store_true', default=False, help="Run on local or ngrok")
        parser.add_argument('--host', type=str, default='localhost', help="Local IP")
        parser.add_argument('--port', type=int, default=5000, help="Local port")
        parser.add_argument('--debug', action='store_true', default=False, help="Run app in debug mode")
        args = parser.parse_args()

        app = create_app()

        basedir = os.path.abspath(os.path.dirname(__file__))
        upload_folder_path = os.path.join(basedir, 'static', 'assets', 'uploads')
        csv_folder_path = os.path.join(basedir, 'static', 'assets', 'csv')
        detection_folder_path = os.path.join(basedir, 'static', 'assets', 'detection')
        segmentation_folder_path = os.path.join(basedir, 'static', 'assets', 'segmentation')
        metadata_folder_path = os.path.join(basedir, 'metadata')

        os.makedirs(upload_folder_path, exist_ok=True)
        os.makedirs(csv_folder_path, exist_ok=True)
        os.makedirs(detection_folder_path, exist_ok=True)
        os.makedirs(segmentation_folder_path, exist_ok=True)
        os.makedirs(metadata_folder_path, exist_ok=True)

        if args.ngrok:
            public_url = ngrok.connect(args.port).public_url
            print(f" * ngrok tunnel \"{public_url}\" -> \"http://127.0.0.1:{args.port}/\"")
            app.config['BASE_URL'] = public_url
        else:
            app.config['BASE_URL'] = f"http://{args.host}:{args.port}"

        app.run(host=args.host, port=args.port, debug=args.debug)

