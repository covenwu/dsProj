from openai import OpenAI

client = OpenAI(
    api_key="sk-UXCWFj2Md7688d70e7deT3BLbkFJ6696f0FAb26746E78Dd2",#e4aa2de7-78a9-4793-b132-ddf79269a35e",#"sk-eb1a5dee66374fb7bac030255fcd07f2",
    base_url="https://www.ohmygpt.com/v1"#"https://api.deepseek.com/"
)


import openai

def test_client():
    try:
        # 发送一个简单的文本生成请求
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",  # 假设支持的模型
            messages=[
                {"role": "user", "content": "Hello, how are you?"}
            ],
            stream=True
        )
        
        # 处理流式响应
        for chunk in response:
            # 检查是否有内容
            if hasattr(chunk.choices[0].delta, 'content'):
                print(chunk.choices[0].delta.content, end="", flush=True)
        
        print("\nStream completed successfully.")
        return True
    except Exception as e:
        print("Error:", e)
        return False

if __name__ == "__main__":
    result = test_client()
    if result:
        print("Test passed: Client is working correctly.")
    else:
        print("Test failed: Client is not working correctly.")