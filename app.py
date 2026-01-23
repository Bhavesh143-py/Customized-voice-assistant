# In app.py
from Recorder.Frontend import show_recorder
from Backend.RagAssistant import AIVoiceAssistant

def main():
    #initialize rag assistant
    assistant = AIVoiceAssistant()
    
    def handle_transcription(text):
        global answer
        print("User said:", text)
        answer = assistant.interact_with_llm(text)
        
        # answer = run_rag(text)
        print("AI:", answer)
        # run_tts(answer)

    print("Starting application...")
    show_recorder(handle_transcription)
    print("Application closed.")


if __name__ == "__main__":
    main()
