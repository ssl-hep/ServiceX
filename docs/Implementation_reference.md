# Implementation reference

## API

TODO: 
* make sure I list here only endpoints that don't return a web page.
* make rucio update paths in ES not at the end of the rucio lookup but every 10 file lookups
* update file/path status

### user

* GET /user maybe 

    probably not needed

* GET /users_data


* GET /profile
* GET /users
* GET /authorize/:user_id
* GET /get_requests

### drequest

* GET /drequest_get/:status
* PUT /drequest/status/:id/:status/:info?
* GET /drequest_update/:rid 

    WEB only

* GET /drequest_prepare
* GET /drequest_terminate
* GET /drequest_manage
* POST /drequest_update

### dpath

* GET /dpath/:id
* GET /dpath/last_used/:rid
* POST /dpath/update
* GET /dpath/transform/
* POST /dpath/transform/

## Requests 

### States 

* Defined -> Defining
* Failed
* Prescreened


### State transitions

* 

## Single file 


### States 

* Defined
* Located
* Transforming
* Transformed

### State transitions

*

