'''
serve power and cadence metrics over RESTful API
'''

import argparse
from time import sleep
from flask import jsonify, make_response, Flask
from flask_restful import Api, Resource, reqparse
from multiprocessing import Process, Manager

def obtain_metrics(metrics):
    while True:
        try:
            # power_img, cadence_img = get_power_and_cadence_imgs()

            power = 100
            cadence = 61

            metrics['power'] = power
            metrics['cadence'] = cadence

            print(metrics)
            sleep(1)  # wait for 1 second before next update
            if debug:
                print("Metrics: {}".format(metrics))

        except ValueError as e:
            if debug:
                print("Can't recognize numbers. Is the Peloton Connect window visible? Error: {}".format(e))


class Metrics(Resource):
    def get(self):
        return metrics.copy(), 200


ap = argparse.ArgumentParser()
ap.add_argument("-d", "--debug", type=bool, nargs='?', const=True, default=False, help="Enable debug messages")
ap.add_argument("-p", "--port", type=int, default=5000, help="Webserver port")
args = vars(ap.parse_args())
debug = args["debug"]
port = args["port"]


app = Flask(__name__)
api = Api(app)
api.add_resource(Metrics, "/metrics")

if __name__ == '__main__':
    with Manager() as manager:
        metrics = manager.dict()
        metrics['cadence'] = 0
        metrics['power'] = 0

        p = Process(target=obtain_metrics, args=(metrics,))
        p.start()

        app.run(host='0.0.0.0', port=port, debug=debug)