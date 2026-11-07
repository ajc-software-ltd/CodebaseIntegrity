// JavaScript extraction fixture.
class Engine extends BaseEngine {
    constructor(name) {
        super(name);
    }
    start(mode) {
    }
    static create() {
    }
}

function bootstrap(config) {
    function logStep(step) {
        return step;
    }
    return config;
}

const helper = () => 1;
