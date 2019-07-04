# Implementation reference

## API

TODO: 

# imediate

* make request update return specific code when request not there. Then kafka monitor can delete queue with such a return code. 
* make request buttons on web site correctly behave 
* check that terminate actually terminates paths. Does now really work when request has 10000 files.
* make web site use regular REST endpoints.
* define getters and setters for drequest and dpath variables. functions to go from es to local and back. 
* update file/path status
* there is some mess with "approved." is it in session or in user.
* split web and rest servers.

# scaling

# user friendliness

* add buttons to terminate request
* add visualizations to show progress (kibana visualization)
* add icons to clone request -> just opens create web page and prepopulates with values from the original request.
* get user info in ES. currently most not stored.

### user

* GET /profile - renders profile page. preloads users data from ES. will be simpler once ajax call gets data from /user
* GET /users - renders users page. ajax call gets data from /users_data.

* GET /authorize/:user_id
* GET /get_requests - returns requests data for a user. web called. should not be needed once page makes ajax call to /user/requests/


* GET /user/:user_id?  __validated__
        
    returns json formated user profile data. if called from web interface and user is logged __user_id__ is not needed.

* GET /users_data  __validated__

    returns json formated data on all users

* GET /user/requests/:user_id  __validated__
    
    returns json formated info on all users requests

### drequest

* GET /drequest/status/:status

    for a given request status (eg. Defined) it finds the oldest request in that status. Returns all of that drequest data in json format. 

* GET /drequest/:id __validated__

    for a given request_id it returns all drequest data in json format. 

* PUT /drequest/status/:id/:status/:info?

* PUT /drequest/terminate/:id __testing__ __NOT validated__

    Sets status to Terminated for a given request_id and all the related paths.

* PUT /drequest/events_processed/:id/:events __validated__

    for a given request_id increments number of events processed by _events_. If all the events were processed, request status is set to _Done_.

* POST /drequest/create __validated__

    json document must contain: userid, name, dataset, branches, events requested, optionaly: request description.
    eg.
    {
        "userid":"a51dbd7e-d274-11e5-9b11-9be347a09ce0",
        "name": "test x",
        "dataset": "mc15_13TeV:mc15_13TeV.361106.PowhegPythia8EvtGen_AZNLOCTEQ6L1_Zee.merge.DAOD_STDM3.e3601_s2576_s2132_r6630_r6264_p2363_tid05630052_00",
        "description": "just a test",
        "columns":["Electrons.pt()","Electrons.eta()","Electrons.phi()"],
        "events":123456
    }

* POST /drequest/update

    updates all the posted info.

#### WEB only
* GET /wrequest_update/:rid 
* GET /wrequest_prepare
* GET /wrequest_terminate
* GET /wrequest_manage
* POST /wrequest_update

### dpath

* POST /dpath/create

    to be used by DID-finder

* GET /dpath/transform/

    used by transformer. If there is a path that is in _Validated_ state it is updated to _Transforming_ and returned to the transformer.

* GET /dpath/transform/:rid/:status

    returns data on a path belonging to _rid_ request and in certain status.

* PUT /dpath/transform/:id/:status

    transformer returns :id, status

#### Unused for now
* GET /dpath/:id  __validated__

    returns all the data about path

* GET /dpath/last_used/:rid

## Requests states and transitions

* After web or CLI request creation request is in *Created*
* DID-finder will change it first to *LookingUp* and on finish to *LookedUp* or *Failed*
* Validator will change it to *Validated* or *Failed*
* First transformer will change state to *Processing* or *Failed*
* Last transformer will change it to *Delivered*
* Last processed will change it to *Processed*


## Single file states and transitions

* DID-finder will create paths in state *Created*
* Validator will change them to *Validated*
* Transformer will first move them to *Transforming*
* Transformer will change them to *Failed* or *Transformed*



transformer workflow:

1. gets dpath to process (_id, rid, path, file_events)
1. gets drequest connected to that dpath (columns, events_transformed, events_transforming, events_requested )
1. if transformation needed 
    1. update dpath status to _Transforming_
    1. update drequest events_transforming
    else
    1. update dpath status to NotNeeded
1. once transformation done update dpath status to _Transformed_, update drequest events_tranformed, events_transforming, and if needed drequest status to _Transformed_.
