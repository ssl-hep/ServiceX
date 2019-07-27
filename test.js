
class Request {
    constructor() {
        this.name = 'name Undefined';
        this.user = 'user Undefined';
        this.description = 'description Undefined';
        this.dataset = 'dataset Undefined';
        this.columns = 'columns Undefined';
        this.created_at = new Date().getTime();
        this.modified_at = new Date().getTime();
        this.status = 'Created';
        this.info = '';
        this.paused_transforms = false;
        this.events_processed = 0;
        this.events_served = 0;
        this.events = 0;
        this.kafka_lwm = 0;
        this.kafka_hwm = 0;
        this.redis_messages = 0;
        this.redis_consumers = 0;
    }
}

class cESbackend {

}

class hRequests {
    constructor() {
        this.reqs = {};
    }

    addRequest(req_id, req) {
        console.log(`added req_id: ${req_id}`)
        this.reqs[req_id] = req;
    }

    getRequest(req_id) {
        console.log(`getting req_id: ${req_id}`)
        if (this.reqs[req_id]) {
            console.log('found');
            return this.reqs[req_id];
        }
        else console.log('not found');
    }
    publish() {

    }
}


const hR = new hRequests();
hR.addRequest('randString', new Request());
console.log(hR.getRequest('randString'));
