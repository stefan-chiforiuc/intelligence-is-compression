// Cold-start workload: do essentially nothing, as fast as possible.
//
// Everything this program measures happens BEFORE your business logic runs:
// process spawn, dynamic linking, V8 + Node bootstrap, module resolution.
// That fixed cost is what you pay on every single serverless invocation and on
// every pod restart during a rolling deploy.
//
// Node's number here is almost entirely V8 heap setup and Node's own JS
// bootstrap. Note that this file imports nothing: in a real service, module
// resolution over a deep node_modules tree often costs MORE than the runtime
// boot itself. Bundling to a single file is the cheapest cold-start win there
// is in the Node world.

const n: number = process.argv.length > 2 ? Number(process.argv[2]) : 1;
console.log(`ready ${n * 2}`);
