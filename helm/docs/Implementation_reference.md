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

* GET /drequest/status/:status
* PUT /drequest/status/:id/:status/:info?
* POST /drequest/update

    updates all the posted info.

#### WEB only
* GET /drequest_update/:rid 
* GET /drequest_prepare
* GET /drequest_terminate
* GET /drequest_manage
* POST /drequest_update

### dpath

* POST /dpath/create

    to be used by DID-finder

* GET /dpath/transform/

    to be used by transformer

* PUT /dpath/transform/:id/:status

    transformer returns :id, status

#### Unused for now
* GET /dpath/:id
* GET /dpath/last_used/:rid

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

