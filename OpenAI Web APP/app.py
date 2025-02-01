from flask import Flask, render_template, request, jsonify
from openai import OpenAI
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
client = OpenAI()

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/chat', methods=['POST'])
def chat():
    data = request.json
    messages = data.get('messages', [])
    
    try:
        response = client.chat.completions.create(
            model="o3-mini",
            messages=messages
        )
        
        # Convert CompletionTokensDetails to dictionary
        completion_tokens_details = {
            'reasoning_tokens': response.usage.completion_tokens_details.reasoning_tokens,
            'accepted_prediction_tokens': response.usage.completion_tokens_details.accepted_prediction_tokens,
            'rejected_prediction_tokens': response.usage.completion_tokens_details.rejected_prediction_tokens
        }
        
        return jsonify({
            'response': response.choices[0].message.content,
            'usage': {
                'total_tokens': response.usage.total_tokens,
                'completion_tokens_details': completion_tokens_details
            }
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)