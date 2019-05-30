# Implementation reference

## API

TODO: 
* make sure I list here only endpoints that don't return a web page.
* rename endpoints for web to start with w
* remove swagger endpoints
* define getters and setters for drequest and dpath variables. functions to go from es to local and back. 
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
* GET /drequest/:id
* PUT /drequest/status/:id/:status/:info?
* POST /drequest/update

    updates all the posted info.

#### WEB only
* GET /wrequest_update/:rid 
* GET /drequest_prepare
* GET /drequest_terminate
* GET /drequest_manage
* POST /wrequest_update

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
* Transforming
* Transformed

### State transitions

*



transformer workflow:

1. gets dpath to process (_id, rid, path, file_events)
1. gets drequest connected to that dpath (columns, events_transformed, events_transforming, events_requested )
1. if transformation needed 
    1. update dpath status to _Transforming_
    1. update drequest events_transforming
    else
    1. update dpath status to NotNeeded
1. once transformation done update dpath status to _Transformed_, update drequest events_tranformed, events_transforming, and if needed drequest status to _Transformed_.
