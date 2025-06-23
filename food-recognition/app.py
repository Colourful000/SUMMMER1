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

client = OpenAI(
    api_key="sk-58530a01a7a94d66a92c010a8a86f0a9",
    base_url="https://api.deepseek.com"
)
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
                flash('Login successful!', 'success')  # ← 这里
                return redirect(url_for('dashboard'))
            else:
                flash('Invalid username or password', 'danger')  # ← 这里
                return redirect(url_for('login'))
        return render_template('login.html', show_register=False)


    # -------- 用户主页 dashboard --------
    @app.route('/dashboard')
    def dashboard():
        if 'user_id' not in session:
            flash('Please log in first!')
            return redirect(url_for('login'))
        user = User.query.get(session['user_id'])
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

            # 1. 保存上传
            filename, filepath, filetype = process_upload_file(request)

            # 2. 检测（多返回 result_dict）
            out_name, output_path, output_type, result_dict = process_image_file(
                filename,
                filepath,
                "yolov8s",
                False,  # tta
                False,  # ensemble
                0.15,  # min_conf
                0.5,  # min_iou
                False,  # enhanced
                False  # segmentation
            )

            # 3. 读取csv结果（兜底）
            _, csv_name1, csv_name2 = process_output_file(output_path)

            # 4. 提取食物和营养
            if result_dict and 'names' in result_dict and 'scores' in result_dict:
                idx = int(np.argmax(result_dict['scores']))
                food_name = result_dict['names'][idx]
                nutrients = {}
                for k in ['calories', 'protein', 'fat', 'carbs', 'fiber']:
                    if k in result_dict:
                        try:
                            nutrients[k] = result_dict[k][idx]
                        except Exception:
                            nutrients[k] = None
                    else:
                        nutrients[k] = None
                if all(v is None for v in nutrients.values()):
                    nutrients = get_nutrient_from_db(food_name)
            else:
                food_name, nutrients = extract_food_and_nutrients(csv_name1)

            # 5. 加入用户个性化资料（关键！）
            user_info = {}
            meal_type = request.form.get('tag')
            if 'user_id' in session:
                user = User.query.get(session['user_id'])
                if user:
                    user_info = {
                        "gender": user.gender,
                        "age": user.age,
                        "height": user.height,
                        "weight": user.weight,
                        "diet_goal": user.diet_goal,
                        "special_diet": user.special_diet,
                        "activity_level": user.activity_level
                    }

            # 提取“餐次标签”
            tag = request.form.get('tag')

            # 6. 调用 LLM，传入餐次
            data = {"food": food_name, "nutrients": nutrients, "user_info": user_info, "meal_type": meal_type}
            system_prompt = (
                "You are a board-certified nutritionist. "
                "The nutrient data provided is **per 100g serving**. "
                "If the food choice is strongly misaligned with the user's goal or dietary guidelines, do not artificially highlight minor positives—be strict and direct in your assessment."
                "Give a concise, highly personalized analysis based on the user's profile (age, gender, height, weight in kg, diet goal, special diet, activity level) and the meal type (e.g. breakfast, lunch, snack, late night). "
                "Clearly explain potential health impacts, risks, and actionable dietary advice relevant to the user's goals. "
                "Do NOT use quotation marks or code blocks. "
                "All output must be clear, well-structured professional English, about 120 words."
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

            # 7. 保存历史记录（如用户选择保存）
            save_history = request.form.get('save_history') == 'true'
            if save_history and 'user_id' in session:
                tag = request.form.get('tag')
                history = AnalysisHistory(
                    user_id=session['user_id'],
                    food_name=food_name,
                    nutrients=json.dumps(nutrients),
                    ai_advice=ai_advice,
                    tag=tag
                )
                db.session.add(history)
                db.session.commit()

            return render_template(
                'analyze_result.html',
                food_name=food_name,
                nutrients=nutrients,
                ai_advice=ai_advice
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
        # 确保 tmp 文件夹存在
        if not os.path.exists('./tmp'):
            os.makedirs('./tmp')
        audio_file = request.files['audio']
        audio_path = f"./tmp/{audio_file.filename}"
        audio_file.save(audio_path)
        # 转文字
        result = model.transcribe(audio_path, language='en')
        # 处理完后立刻删除临时文件
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

            # --- 查询营养库 ---
            import pandas as pd
            csv_file = 'nutrition_db.csv'  # 改成你的实际路径
            nutrients = {k: None for k in ['calories', 'protein', 'fat', 'carbs', 'fiber']}
            try:
                df = pd.read_csv(csv_file)
                result = df[df['name'].str.lower().str.contains(food_text.lower())]
                if not result.empty:
                    row = result.iloc[0]
                    nutrients = {
                        'calories': float(row['calories']),
                        'protein': float(row['protein']),
                        'fat': float(row['fat']),
                        'carbs': float(row['carbs']),
                        'fiber': float(row['fiber']),
                    }
            except Exception as e:
                print('CSV 查找异常:', e)
                # nutrients 仍为 None

            # --- 加入用户个性化资料 ---
            user_info = {}
            meal_type = request.form.get('tag')
            if 'user_id' in session:
                user = User.query.get(session['user_id'])
                if user:
                    user_info = {
                        "gender": user.gender,
                        "age": user.age,
                        "height": user.height,
                        "weight": user.weight,
                        "diet_goal": user.diet_goal,
                        "special_diet": user.special_diet,
                        "activity_level": user.activity_level
                    }

            # --- AI 分析 ---
            data = {"food": food_text, "nutrients": nutrients, "user_info": user_info, "meal_type": meal_type}
            system_prompt = (
                "You are a board-certified nutritionist. "
                "The nutrient data provided is **per 100g serving**. "
                "If the food choice is strongly misaligned with the user's goal or dietary guidelines, do not artificially highlight minor positives—be strict and direct in your assessment."
                "Give a concise, highly personalized analysis based on the user's profile (age, gender, height, weight in kg, diet goal, special diet, activity level) and the meal type (e.g. breakfast, lunch, snack, late night). "
                "Clearly explain potential health impacts, risks, and actionable dietary advice relevant to the user's goals. "
                "Do NOT use quotation marks or code blocks. "
                "All output must be clear, well-structured professional English, about 120 words."
            )

            prompt = build_prompt(data)
            ai_advice = ""
            try:
                response = client.chat.completions.create(
                    model="deepseek-reasoner",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt}
                    ],
                    stream=False
                )
                ai_advice = response.choices[0].message.content
            except Exception as e:
                ai_advice = f"AI analysis failed: {e}"

            # --- 保存历史记录 ---
            import json
            if save_history and 'user_id' in session:
                history = AnalysisHistory(
                    user_id=session['user_id'],
                    food_name=food_text,
                    nutrients=json.dumps(nutrients),
                    ai_advice=ai_advice,
                    tag=tag
                )
                db.session.add(history)
                db.session.commit()

            return render_template(
                'analyze_result.html',
                food_name=food_text,
                nutrients=nutrients,
                ai_advice=ai_advice
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
        user = User.query.get(session['user_id'])
        if request.method == 'POST':
            # 获取表单内容并保存
            user.gender = request.form.get('gender')
            user.age = request.form.get('age')
            user.height = request.form.get('height')
            user.weight = request.form.get('weight')
            user.diet_goal = request.form.get('diet_goal')
            user.special_diet = request.form.get('special_diet')
            user.activity_level = request.form.get('activity_level')
            # 头像上传后端后续补充
            db.session.commit()
            flash('Profile updated successfully!', 'success')
            return redirect(url_for('dashboard'))
        return render_template('profile.html', user=user)

    from datetime import datetime, timedelta

    # 选择日期页面
    @app.route('/dietician_select', methods=['GET'])
    def dietician_select():
        if 'user_id' not in session:
            flash('Please log in first!')
            return redirect(url_for('login'))
        return render_template('dietician_select.html')

    # 结果分析页面
    from flask import request, render_template, flash, redirect, url_for, session
    from datetime import datetime, timedelta
    import json

    @app.route('/dietician_result', methods=['GET', 'POST'])
    def dietician_result():
        if 'user_id' not in session:
            flash('Please log in first!')
            return redirect(url_for('login'))

        # 支持GET和POST参数，方便页面回跳
        start_date = request.form.get('start_date') or request.args.get('start_date')
        end_date = request.form.get('end_date') or request.args.get('end_date')
        user_message = request.form.get('user_message', '').strip() if request.method == 'POST' else ''

        # 日期解析
        try:
            start = datetime.strptime(start_date, "%Y-%m-%d")
            end = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)  # 包含结束当天
        except Exception:
            flash('Invalid date.')
            return redirect(url_for('dietician_select'))

        # 查询历史
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
                "food": record.food_name,
                "nutrients": nutrients,
                "tag": record.tag,
                "ai_advice": record.ai_advice
            })

        # 构建基础营养历史上下文
        base_context = (
            "Here are the user's nutrition records for the selected dates:\n"
        )
        for h in history_summaries:
            base_context += f"Food: {h['food']}, Tag: {h['tag']}, Nutrients: {h['nutrients']}, Previous AI Advice: {h['ai_advice']}\n"

        # 统一AI风格的system prompt
        system_prompt = (
            "You are a warm, conversational, board-certified dietician. "
            "When you answer, you must only provide nutrition advice, never discuss anything else. "
            "You always consider the user's historical nutrition records provided below when answering. "
            "Never use any lists, bullets, or special formatting. Speak in a friendly, conversational tone. "
            "Never use dashes, hyphens, quotes, or any kind of list or numbered format. "
            "Respond only with full sentences, like you’re chatting face to face. "
            "Summarize what stands out, what concerns you, and what to change, but speak in a natural, supportive, flowing paragraph. "
            "Maximum 180 words."
        )

        ai_summary = ""
        ai_reply = None

        # 首次打开或刷新，仅给分析总结
        if request.method == 'GET' or not user_message:
            if history_summaries:
                summary_prompt = (
                        base_context +
                        "Please review these records and give the user a natural, spoken-style summary of their nutrition, pointing out main strengths and improvements, without using any lists or formatting."
                )
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
            # 首次不显示对话内容
            return render_template(
                'dietician_result.html',
                summary=ai_summary,
                start_date=start_date,
                end_date=end_date,
                user_message=None,
                ai_reply=None
            )

        # 用户提交提问
        else:
            chat_prompt = (
                    base_context +
                    f"\nUser's question: {user_message}\n"
                    "Please answer only as a nutritionist, referencing the user's nutrition history above. "
                    "Never discuss anything outside of nutrition. Speak like a person, in normal sentences, not in lists or points."
                    "Maximum 30 words."
            )
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
                'dietician_result.html',
                summary=None,  # 提问时不重复summary
                start_date=start_date,
                end_date=end_date,
                user_message=user_message,
                ai_reply=ai_reply
            )

    return app


def get_nutrient_from_db(food_name):
    import pandas as pd
    df = pd.read_csv('nutrition_db.csv')
    result = df[df['name'].str.lower().str.contains(food_name.lower())]
    if not result.empty:
        row = result.iloc[0]
        return {
            'calories': float(row['calories']),
            'protein': float(row['protein']),
            'fat': float(row['fat']),
            'carbs': float(row['carbs']),
            'fiber': float(row['fiber']),
        }
    return {k: None for k in ['calories', 'protein', 'fat', 'carbs', 'fiber']}




parser = argparse.ArgumentParser('Online Food Recognition')
parser.add_argument('--ngrok', action='store_true', default=False, help="Run on local or ngrok")
parser.add_argument('--host', type=str, default='localhost', help="Local IP")
parser.add_argument('--port', type=int, default=5000, help="Local port")
parser.add_argument('--debug', action='store_true', default=False, help="Run app in debug mode")
args = parser.parse_args()

if __name__ == '__main__':
    app = create_app()

    for folder in [UPLOAD_FOLDER, DETECTION_FOLDER, SEGMENTATION_FOLDER, CSV_FOLDER, METADATA_FOLDER]:
        os.makedirs(folder, exist_ok=True)

    if args.ngrok:
        print("Enter your authtoken, which can be copied from https://dashboard.ngrok.com/get-started/your-authtoken")
        conf.get_default().auth_token = getpass.getpass()
        public_url = ngrok.connect(args.port).public_url
        print(f" * ngrok tunnel \"{public_url}\" -> \"http://127.0.0.1:{args.port}/\"")
        app.config['BASE_URL'] = public_url
    else:
        app.config['BASE_URL'] = f"http://{args.host}:{args.port}"

    app.run(host=args.host, port=args.port, debug=True)
