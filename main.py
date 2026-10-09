from flask import Flask, render_template, request
from flask_htmx import HTMX

app = Flask(__name__)
htmx = HTMX(app)

@app.route('/')
def main():
    return render_template('index.html')


@app.route('/search', methods=['POST'])
def search():
    query = request.form.get('query', '')
    # Pour l'instant, un retour HTMX factice pour tester la réactivité
    return f"""
    <div class="p-4 bg-gray-100 rounded-lg border mt-4">
        <p class="font-bold">Question reçue : "{query}"</p>
        <p class="text-sm text-gray-600 mt-2">Le moteur RAG est prêt à être connecté...</p>
    </div>
    """

if __name__ == "__main__":
    app.run(debug=True)
