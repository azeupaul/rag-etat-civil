from flask import Flask, render_template
from flask_htmx import HTMX

app = Flask(__name__)
htmx = HTMX(app)

@app.route('/', methods=['GET', 'POST'])
def main():
    if htmx:
        return render_template('partials/clic.html', htmx=True)
    return render_template('index.html')

if __name__ == "__main__":
    app.run(debug=True)