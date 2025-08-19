from flaskr import app

if __name__ == "__main__":
    #app.run() # run only locally on computer on 127.0.0.1:5000
    app.run(host='0.0.0.0', port=8080) # run locally within the network (ex. wifi), ip will be assigned automatically