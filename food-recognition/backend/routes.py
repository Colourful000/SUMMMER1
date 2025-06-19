from flask_cors import cross_origin
from flask import request, render_template, redirect, make_response
from flask import jsonify
from openai import OpenAI
from .utils import process_webcam_capture, process_url_input, process_image_file, process_output_file, process_upload_file

# DeepSeek 客户端配置，可以写在 set_routes 之前，或者全局
client = OpenAI(
    api_key="sk-58530a01a7a94d66a92c010a8a86f0a9",
    base_url="https://api.deepseek.com"
)

def build_prompt(data):
    food = data.get('food', '未知食物')
    nutrients = data.get('nutrients', {})
    user_info = data.get('user_info', {})
    s = f"请分析如下食物的营养成分，并根据用户目标给出简明建议。\n"
    s += f"食物：{food}\n"
    s += f"营养成分：\n"
    for k, v in nutrients.items():
        s += f"{k}: {v}\n"
    if user_info:
        s += f"用户信息：{user_info}\n"
    else:
        s += "用户信息：无\n"
    s += "分析和建议："
    return s

def set_routes(app):





    @app.route('/analyze', methods=['POST', 'GET'])
    @cross_origin(supports_credentials=True)
    def analyze():
        if request.method == 'POST':
            out_name, filepath, filename, filetype, csv_name1, csv_name2 = None, None, None, None, None, None

            if 'webcam-button' in request.form:
                filename, filepath, filetype = process_webcam_capture(request)

            elif 'url-button' in request.form:
                filename, filepath, filetype = process_url_input(request)

            elif 'upload-button' in request.form:
                filename, filepath, filetype = process_upload_file(request)

            # Get all inputs in form
            min_iou = float(request.form.get('threshold-range', 50)) / 100
            min_conf = float(request.form.get('confidence-range', 15)) / 100
            model_types = (request.form.get('model-types') or 'YOLOv8s').lower()
            enhanced = request.form.get('enhanced') == 'on'
            ensemble = request.form.get('ensemble') == 'on'
            tta = request.form.get('tta') == 'on'
            segmentation = request.form.get('seg') == 'on'

            if filetype == 'image':
                out_name, output_path, output_type = process_image_file(filename, filepath, model_types, tta, ensemble, min_conf, min_iou, enhanced, segmentation)
            else:
                return render_template('detect-input-url.html', error_msg="Invalid input url!!!")

            filename, csv_name1, csv_name2 = process_output_file(output_path)

            if 'url-button' in request.form:
                return render_template('detect-input-url.html', out_name=out_name, segname=output_path, fname=filename, output_type=output_type, filetype=filetype, csv_name=csv_name1, csv_name2=csv_name2)

            elif 'webcam-button' in request.form:
                return render_template('detect-webcam-capture.html', out_name=out_name, segname=output_path, fname=filename, output_type=output_type, filetype=filetype, csv_name=csv_name1, csv_name2=csv_name2)

            return render_template('detect-upload-file.html', out_name=out_name, segname=output_path, fname=filename, output_type=output_type, filetype=filetype, csv_name=csv_name1, csv_name2=csv_name2)

        return redirect('/')




    @app.after_request
    def add_header(response):
        # Include cookie for every request
        response.headers.add('Access-Control-Allow-Credentials', True)

        # Prevent the client from caching the response
        if 'Cache-Control' not in response.headers:
            response.headers['Cache-Control'] = 'public, no-store, no-cache, must-revalidate, post-check=0, pre-check=0, max-age=0'
            response.headers['Pragma'] = 'no-cache'
            response.headers['Expires'] = '-1'
        return response