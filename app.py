from flask import Flask, render_template, request

app = Flask(__name__)

@app.route('/')
def home():
    return render_template("home.html")

@app.route('/quote', methods=['GET', 'POST'])
def quote():
    if request.method == 'POST':
        tow_type = request.form.get('tow_type')
        mileage = float(request.form.get('mileage', 0))
        extra_services = request.form.getlist('extra_services')
        rate = 4 if tow_type == 'flatbed' else 3
        estimated_cost = mileage * rate + len(extra_services) * 20
        return render_template('quote.html', result=estimated_cost)
    return render_template('quote.html', result=None)

if __name__ == '__main__':
    app.run(debug=True)
