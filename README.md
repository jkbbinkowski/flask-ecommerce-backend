# FLASK E-COMMERCE BACKEND

## !!! THIS APPLICATION IS STILL UNDER DEVELOPMENT !!!

## OVERVIEW
### Before working with the application, make sure to read LICENSE file.
This is fully functional Flask-based backend for e-commerce store.<br>
It's designed to be as little resource and bandwith consuming as possible.<br>
The app is passing all efficiency Google SpeedTests above 90 points.<br>
Unfortunately due to license issues I cannot upload templates and static files.<br>
This repository is still missing few crucial elements for the application to work, they will be added in the future.<br>
<br>
Feel free to contact me if you need help or additional resources (like those listed below) required to run the application.<br>
<br>
So far not included in the repository:<br>
- MYSQL database schema

## REQUIREMENTS
- Python3
- MYSQL-server
- Redis-server

## GETTING STARTED
1. Create new virtual environment in root directory: 
```python3 -m venv .venv```

2. Activate the virtual environment: 
```. .venv/bin/activate```

3. Install venv dependencies: 
```pip install -r requirements.txt```

4. Configure the application based on your preferences. Below you will find guidelines for the configuration.

## CONFIGURATION
The application consists of few configuration files.<br>
Make sure to configure it properly before getting started.<br>
<b>All examples of the configuration files, are located in the "examples" folder.<br>
The location of all the files and folders shall be as is, without "examples" folder.</b><br>
<b>Make sure that all the paths include slashes as provided in the examples file.</b><br>
Below you will find description for each configuration file.<br>

### config.ini
This file contains non-sensitive configuration for the application. Below you will find the description of each part of the configuration file.<br>
Remove "example." header from the file.<br>
| Name | Description |
| ---- | ----------- |
| APP | Basic configuration of the app used by Flask. Check flask configuration guidelines for non-binary values. |
| REDIS | Redis configuration used by Redis-server. |
| AUTH | Configuration for authorization used by werkzeug.security module. |
| GLOBAL | Global configuration not related directly to flask application. |
| VISUAL | Variables, that are meant to be used by Jinja2 while rendering the templates. None of them is used by the backend itself. |
| ACTIONS | Action endpoints, which are parsed at the end of the url for different actions during requests (ex. POST, DELETE, PUT, PATCH), used directly by backend. |
| ENDPOINTS | Endpoints used directly by backend. |
| TITLES | Titles of each endpoint. They are meant to be used by Jinja2 while rendering the templates. None of them is used by the backend itself. |
| REDIS_QUEUES | Names of the queues used by Redis-server. |
| EMAIL_PATHS | Paths to email templates, used for transactional emails. | 
| EMAIL_SUBJECTS | Subjects of emails, used for transactional emails. | 
| TRANSACTIONAL_EMAIL | Non-sensitive configuration for transactional emails. | 
| STATIC_PDF | Names of files located in /flaskr/static/pdf. They are meant to be used by Jinja2 while rendering the templates. None of them is used by the backend itself. |
| PRODUCTS | Configuration for store such as visibility per page, sorting options. |
| COOKIE_NAMES | Names of the cookie files used by the application. |

### .env
This file contains all the sensitive configuration.<br>
<b>NEVER</b> share the contents of this file with anyone.<br>
Remove "example." header from the file.<br>
<b>WORKING_DIR</b> is the directory in which application is located.<br>
Example: <b>&sol;user&sol;flask-app&sol;</b> (!!! the slash at the end is crucial !!!)<br>
Rest of the variables in this file are self-explanatory.<br>

### static
Static directory contains it's own README file, with recommendations for creating static files.<br>

### json
Json directory contains files in JSON format. Those files are used by the backend to return specific messages for some requests other than GET.<br>
They are self-explanatory.<br>
<b>IMPORTANT: make sure that messages in errors.json are parsed as array. This allows you to return more than one independed message per request (ex. different validation errors for the user while creating new password).</b>
See example below (<b>"Requests other than GET"</b> section) of how they should be treated by the frontend.<br>

### init.py
init.py file contains some lines, that might require configuration.<br>
<b>ASSETS CONFIG</b> section requires configuration, based on how your static files look.<br>
The configuration provided in those lines is an example.<br>
For more detailed description, check Flask-Assets module documentation.<br>
Minification of the files makes sure that all requests are as little bandwith consuming as possible.<br>
<b>In production you should always use minified files when possible.</b>

## Workers used by application
There are several workes, that are used as external services, which help application run as designed.<br>
Workers are located in scripts folder.<br>
Those workers should run periodically. The approach "looping" should be based on your own needs (whenever you need to use infinite loops, systemd services or docker).<br>
- expired_db.py - removes outdated rows in the database (ex. expired password reset tokens)
- mail_handler.py - most of the emails, which are not crucial for application to run, are being scheduled in redis queue. This scripts is obtaining those emails, that are later on being send to the user. This approach ensures efficiency of the flask application. (some emails that are crucial or time sensitive (ex. password reset emails) are being send directly during the request, so in case of an external error like mail server not available, the user will see error message).

## Requests other than GET
The application is designed to use JavaScript for most of the requests that aren't GET requests.<br>
This is also recommended approach when using HTML forms.<br>
The ids for the inputs and types of requests can be found in .py files, in validation functions at the end of each file.<br>
Status codes returned by each request can be found in the .py files, messages can be adjusted using JSON files.<br>
Below you have an example of JavaScript function, that is used for sign-up.<br>
<b>All requests other than GET require CSRF-token being parsed as below.<br>
CSRF-token can be obtained as Jinja2 variable, using ``` {{ csrf_token() }} ```.</b><br>
```
function r() {
    document.getElementById('sign-up-btn').disabled = true;
    var i = document.getElementsByName('sign-up-form');

    var x = new XMLHttpRequest();
    x.onreadystatechange = function () {
        if (x.readyState == XMLHttpRequest.DONE) {
            document.getElementById('sign-up-btn').disabled = false;
            if (x.status == 201){
                // x.response; - success message obtained as a response
                // it's recommended to use modal for displaying after-request message
            } else if (x.status == 400){
                // JSON.parse(x.response); - error messages obtained as a response
                // it's recommended to use modal for displaying after-request messages
                // it shall be parsed as JSON, as described above in JSON configuration section
            } else {
                sem(x.status);
            };
        };
    };
    x.open("POST", er);
    x.setRequestHeader("X-CSRFToken", ct);
    var b = {};
    for (var j = 0; j < i.length; j++) {
        if (i[j].type === 'checkbox') {
            b[i[j].id] = i[j].checked;
        } else {
            b[i[j].id] = i[j].value;
        };
    };
    x.send(JSON.stringify(b));
};
```

## RUNNING THE APPLICATION (development only)
1. Configure file "dev_server.py" file based on the area in your local network you want to have access to the application from.
2. Activate the virtual environment: 
```. .venv/bin/activate```
3. Run the application: ```python3 dev_server.py```

## DEPLOYING TO PRODUCTION
1. Configure APP section in config.ini file based on flask guidelines for deploying to production.
2. Set secure FLASK_SECRET_KEY in .env file based on flask guidelines for deploying to production.
3. Application is designed to be served using Flask-Nginx-Gunicorn stack. Example of how to deploy it can be found online.<br>
<br>
<b>Never deploy the application for public access using development server. This can lead to various security issues. Before deploying to production, make sure that you understand how flask based application should be deployed to production. Always use WSGI middleware (like gunicorn), reverse proxy server (like NGINX).</b><br>
It's recommended to use https certificate for each request. Certificate can be obtained using "Let's Encrypt Certbot". After installing the certificate, make sure to change config['GLOBAL']['domain'] to https.
