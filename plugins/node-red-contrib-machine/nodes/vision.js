module.exports = function (RED) {
  const operations = ['preprocess', 'locate', 'geometry', 'measure', 'barcode', 'ocr', 'defects', 'yolo', 'yolo_segment', 'cloud_filter', 'cloud_plane', 'cloud_cluster', 'cloud_measure', 'cloud_height', 'cloud_register'];
  for (const operation of operations) {
    function VisionNode(config) {
      RED.nodes.createNode(this, config);
      let closed = false;
      this.on('close', () => { closed = true; });
      this.on('input', async (msg, send, done) => {
        this.status({ fill: 'blue', shape: 'dot', text: '处理中' });
        try {
          const image = msg.image || (typeof msg.payload === 'string' ? msg.payload : msg.payload?.image);
          const cloud = msg.cloud || msg.payload?.cloud;
          const reference = msg.reference || msg.payload?.reference || config.reference;
          const params = { ...JSON.parse(config.params || '{}'), ...(msg.visionParams || {}) };
          const output = await RED.settings.machineVision.run({ operation, image, cloud, reference, params });
          if (closed) return done();
          msg.image = operation === 'preprocess' ? output.annotatedImage : operation === 'yolo_segment' && params.output === 'mask' ? output.maskImage : image;
          if(output.cloud || cloud)msg.cloud = output.cloud || cloud;
          msg.vision = output;
          msg.payload = output.result;
          this.status(output.result?.found===false&&['cloud_register','locate'].includes(operation)?{fill:'yellow',shape:'ring',text:operation==='locate'?'未检出目标':'定位未通过'}:{ fill: 'green', shape: 'dot', text: `${output.elapsedMs} ms` });
          // Output 1 carries structured results; output 2 is a dashboard image message.
          send([msg, { ...msg, payload: operation.startsWith('cloud_') ? output.cloud : output.annotatedImage }]);
          done();
        } catch (error) {
          if (!closed) this.status({ fill: 'red', shape: 'ring', text: '失败' });
          done(error);
        }
      });
    }
    RED.nodes.registerType(`machine-${operation}`, VisionNode);
  }
};
