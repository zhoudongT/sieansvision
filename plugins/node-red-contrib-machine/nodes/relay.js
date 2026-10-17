module.exports = function (RED) {
  function MachineRelay(config) {
    RED.nodes.createNode(this, config);
    this.on('input', (msg, send, done) => {
      msg.machine = { label: config.label || 'demo', timestamp: Date.now() };
      this.status({ fill: 'green', shape: 'dot', text: '已处理' });
      send(msg);
      done();
    });
    this.on('close', () => this.status({}));
  }
  RED.nodes.registerType('machine-relay', MachineRelay);
};
