# Implementation reference

## API

TODO: 

# imediate

* logic in request to make it DONE when events processed finished.
* logic in request to stop transformers when events served > needed.
* make request buttons on web site correctly behave 
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
* GET /users - renders users page. ajax call gets data from /users.

* GET /get_requests - returns requests data for a user. web called. should not be needed once page makes ajax call to /user/requests/

* POST /user/create __validated_NEW__

    json document must contain: userid, username, organization, user, email.
    eg.
    { 
        "userid": "a51dbd7e-d274-11e5-9b11-9be347a09ce0",
        "username": "ivukotic@globusid.org",
        "organization": "University of Chicago",
        "user": "Ilija Vukotic",
        "email": "ivukotic@cern.ch"
    }

    returns OK if successfull, code 500 and a message in case of error.

* PUT /user/approve/:userId __validated_NEw__

* DELETE /user/:userId __validated_NEW__

* GET /user/:userId  __validated_NEW__
        
    returns json formated user profile data.

* GET /users  __validated_NEW__

    returns json formated data on all users

* GET /user/requests/:user_id  __validated_NEW__
    
    returns json formated info on all users requests. Each request gets __reqId__ added. Requests are ordered in descending created_at time.

### drequest

* GET /drequest/status/:status __validated_NEW__

    for a given request status (eg. Defined) it finds the oldest request in that status. Returns all of that drequest data in json format. response includes request id as __reqId__. If nothing found returns nothing.

* GET /drequest/:reqId __validated_NEW__

    for a given request_id it returns all drequest data in json format. If not found returns code 500 and a message.  

* PUT /drequest/status/:reqId/:status/:info? __validated_NEW__

    updates request's status and optionally adds a line to its info log.

* PUT /events_served/:reqId/:pathId/:events __validated_NEW__

    for a given request_id and path_id increments number of events served by _events_.

* PUT /events_processed/:reqId/:events __validated_NEW__

    for a given request_id increments number of events processed by _events_. If all the events were processed, request status is set to _Done_.

* PUT /drequest/terminate/:reqId __validated_NEW__

    Sets status to Terminated for a given request_id and all the related paths.

* POST /drequest/create __validated_NEW__

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
    returns request_id (token) if successfull, code 500 and a message in case of error.

* POST /drequest/update __validated_NEW__

    updates info on: status, dataset_files, dataset_events, dataset_size.

### dpath

* POST /dpath/create __validated_NEW__

    to be used by DID-finder. send json object like this:
    {
	"req_id":"{{req_id}}",
	"adler32":"heusadbasd",
	"file_size":1024,
	"file_events":1000,
	"file_path":"root://dcache-atlas-xrootd.desy.de:1094//pnfs/desy.de/atlas/dq2/atlaslocalgroupdisk/rucio/mc15_13TeV/4a/ad/DAOD_STDM3.05630052._000017.pool.root.1"
    }

* PUT /dpath/status/:pathId/:status/:info? __validated_NEW__

    used by transformer to update path status. Requires path id, new status, optional info

* GET /dpath/:pathId  __validated_NEW__

    returns all the data about path

* GET /dpath/to_transform __validated_NEW__

    used by transformer. If there is a path that is in _Validated_ state it is updated to _Transforming_ and returned to the transformer. pathId is added to returned object.

* GET /dpath/:rid/:status __validated_NEW__

    returns path belonging to _rid_ request and in certain status. Used for example by Validator.



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

1. gets dpath to process (_id, rid, path, file_events). This automatically sets that dpath to _Transforming_.
1. gets drequest connected to that dpath (columns, events_transformed, events_transforming, events_requested )
1. after each batch of events served it updates events_served.
1. once transformation done update dpath status to _Transformed_ or _Error_.

logic in servicex:
1. transformer can send path to Error (reverts status to Validated and increments retry counter). If retry counter goes to 3 autosets to Failed. 
1. Paused is applied only to validated and transforming paths. Unpaused returns everything to validated. 
1. Transformer gets to transform first paths with least number of events left to serve. 

