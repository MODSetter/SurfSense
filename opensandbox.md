AIO opensandbox Example

---
title: Code Interpreter
description: Complete demonstration of running Python code using the Code Interpreter SDK with OpenSandbox.
---

# Code Interpreter Sandbox

Complete demonstration of running Python code using the Code Interpreter SDK.

## Getting Code Interpreter image

Pull the prebuilt image from a registry:

```shell
docker pull sandbox-registry.cn-zhangjiakou.cr.aliyuncs.com/opensandbox/code-interpreter:v1.1.0

# use docker hub
# docker pull opensandbox/code-interpreter:v1.1.0
```

## Start OpenSandbox server [local]

Start the local OpenSandbox server:

```shell
uv pip install opensandbox-server
opensandbox-server init-config ~/.sandbox.toml --example docker
opensandbox-server
```

## Create and access the Code Interpreter Sandbox

```shell
# Install OpenSandbox packages
uv pip install opensandbox opensandbox-code-interpreter

# Run the example (requires SANDBOX_DOMAIN / SANDBOX_API_KEY)
uv run python examples/code-interpreter/main.py
```

The script creates a Sandbox + CodeInterpreter, runs a Python code snippet and prints stdout/result, then terminates the remote instance.

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SANDBOX_DOMAIN` | `localhost:8080` | Sandbox service address |
| `SANDBOX_API_KEY` | _(optional)_ | API key if your server requires authentication |
| `SANDBOX_IMAGE` | `sandbox-registry.cn-zhangjiakou.cr.aliyuncs.com/opensandbox/code-interpreter:v1.1.0` | Sandbox image to use |

## Example output

```text
=== Python example ===
[Python stdout] Hello from Python!

[Python result] {'py': '3.14.2', 'sum': 4}

=== Java example ===
[Java stdout] Hello from Java!

[Java stdout] 2 + 3 = 5

[Java result] 5

=== Go example ===
[Go stdout] Hello from Go!
3 + 4 = 7


=== TypeScript example ===
[TypeScript stdout] Hello from TypeScript!

[TypeScript stdout] sum = 6
```

## Code Interpreter Sandbox from pool

### Start OpenSandbox server [k8s]

Install the k8s OpenSandbox operator, and create a pool:

```yaml
apiVersion: sandbox.opensandbox.io/v1alpha1
kind: Pool
metadata:
  labels:
    app.kubernetes.io/name: sandbox-k8s
    app.kubernetes.io/managed-by: kustomize
  name: pool-sample
  namespace: opensandbox
spec:
  template:
    metadata:
      labels:
        app: example
    spec:
      volumes:
        - name: sandbox-storage
          emptyDir: { }
        - name: opensandbox-bin
          emptyDir: { }
      initContainers:
        - name: task-executor-installer
          image: sandbox-registry.cn-zhangjiakou.cr.aliyuncs.com/opensandbox/task-executor:v0.1.0
          command: [ "/bin/sh", "-c" ]
          args:
            - |
              cp /workspace/server /opt/opensandbox/task-executor && 
              chmod +x /opt/opensandbox/task-executor
          volumeMounts:
            - name: opensandbox-bin
              mountPath: /opt/opensandbox
        - name: execd-installer
          image: sandbox-registry.cn-zhangjiakou.cr.aliyuncs.com/opensandbox/execd:v1.0.21
          command: [ "/bin/sh", "-c" ]
          args:
            - |
              cp ./execd /opt/opensandbox/execd && 
              cp ./bootstrap.sh /opt/opensandbox/bootstrap.sh &&
              chmod +x /opt/opensandbox/execd &&
              chmod +x /opt/opensandbox/bootstrap.sh
          volumeMounts:
            - name: opensandbox-bin
              mountPath: /opt/opensandbox
      containers:
        - name: sandbox
          image: sandbox-registry.cn-zhangjiakou.cr.aliyuncs.com/opensandbox/code-interpreter:v1.1.0
          command:
          - "/bin/sh"
          - "-c"
          - |
            /opt/opensandbox/task-executor -listen-addr=0.0.0.0:5758 >/tmp/task-executor.log 2>&1
          env:
          - name: SANDBOX_MAIN_CONTAINER
            value: main
          - name: EXECD_ENVS
            value: /opt/opensandbox/.env
          - name: EXECD
            value: /opt/opensandbox/execd
          volumeMounts:
            - name: sandbox-storage
              mountPath: /var/lib/sandbox
            - name: opensandbox-bin
              mountPath: /opt/opensandbox
      tolerations:
        - operator: "Exists"
  capacitySpec:
    bufferMax: 3
    bufferMin: 1
    poolMax: 5
    poolMin: 0
```

Start the k8s OpenSandbox server:

```shell
uv pip install opensandbox-server

# replace with your k8s cluster config, kubeconfig etc.
opensandbox-server init-config ~/.sandbox.toml --example k8s
curl -o ~/batchsandbox-template.yaml https://raw.githubusercontent.com/opensandbox-group/OpenSandbox/main/server/opensandbox_server/examples/example.batchsandbox-template.yaml

opensandbox-server
```

### Create and access the Code Interpreter Sandbox (pool)

```shell
# Install OpenSandbox packages
uv pip install opensandbox opensandbox-code-interpreter

# Run the example (requires SANDBOX_DOMAIN / SANDBOX_API_KEY)
uv run python examples/code-interpreter/main_use_pool.py
```

### Pool example output

```text
=== Verify Environment Variable ===
[ENV Check] TEST_ENV value: test

[ENV Result] 'test'

=== Java example ===
[Java stdout] Hello from Java!

[Java stdout] 2 + 3 = 5

[Java result] 5

=== Go example ===
[Go stdout] Hello from Go!
3 + 4 = 7


=== TypeScript example ===
[TypeScript stdout] Hello from TypeScript!

[TypeScript stdout] sum = 6
```

## References

- [Source code on GitHub](https://github.com/opensandbox-group/OpenSandbox/tree/main/examples/code-interpreter)


---
---

# Code interpreter opensandbox example

---
title: Code Interpreter
description: Complete demonstration of running Python code using the Code Interpreter SDK with OpenSandbox.
---

# Code Interpreter Sandbox

Complete demonstration of running Python code using the Code Interpreter SDK.

## Getting Code Interpreter image

Pull the prebuilt image from a registry:

```shell
docker pull sandbox-registry.cn-zhangjiakou.cr.aliyuncs.com/opensandbox/code-interpreter:v1.1.0

# use docker hub
# docker pull opensandbox/code-interpreter:v1.1.0
```

## Start OpenSandbox server [local]

Start the local OpenSandbox server:

```shell
uv pip install opensandbox-server
opensandbox-server init-config ~/.sandbox.toml --example docker
opensandbox-server
```

## Create and access the Code Interpreter Sandbox

```shell
# Install OpenSandbox packages
uv pip install opensandbox opensandbox-code-interpreter

# Run the example (requires SANDBOX_DOMAIN / SANDBOX_API_KEY)
uv run python examples/code-interpreter/main.py
```

The script creates a Sandbox + CodeInterpreter, runs a Python code snippet and prints stdout/result, then terminates the remote instance.

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SANDBOX_DOMAIN` | `localhost:8080` | Sandbox service address |
| `SANDBOX_API_KEY` | _(optional)_ | API key if your server requires authentication |
| `SANDBOX_IMAGE` | `sandbox-registry.cn-zhangjiakou.cr.aliyuncs.com/opensandbox/code-interpreter:v1.1.0` | Sandbox image to use |

## Example output

```text
=== Python example ===
[Python stdout] Hello from Python!

[Python result] {'py': '3.14.2', 'sum': 4}

=== Java example ===
[Java stdout] Hello from Java!

[Java stdout] 2 + 3 = 5

[Java result] 5

=== Go example ===
[Go stdout] Hello from Go!
3 + 4 = 7


=== TypeScript example ===
[TypeScript stdout] Hello from TypeScript!

[TypeScript stdout] sum = 6
```

## Code Interpreter Sandbox from pool

### Start OpenSandbox server [k8s]

Install the k8s OpenSandbox operator, and create a pool:

```yaml
apiVersion: sandbox.opensandbox.io/v1alpha1
kind: Pool
metadata:
  labels:
    app.kubernetes.io/name: sandbox-k8s
    app.kubernetes.io/managed-by: kustomize
  name: pool-sample
  namespace: opensandbox
spec:
  template:
    metadata:
      labels:
        app: example
    spec:
      volumes:
        - name: sandbox-storage
          emptyDir: { }
        - name: opensandbox-bin
          emptyDir: { }
      initContainers:
        - name: task-executor-installer
          image: sandbox-registry.cn-zhangjiakou.cr.aliyuncs.com/opensandbox/task-executor:v0.1.0
          command: [ "/bin/sh", "-c" ]
          args:
            - |
              cp /workspace/server /opt/opensandbox/task-executor && 
              chmod +x /opt/opensandbox/task-executor
          volumeMounts:
            - name: opensandbox-bin
              mountPath: /opt/opensandbox
        - name: execd-installer
          image: sandbox-registry.cn-zhangjiakou.cr.aliyuncs.com/opensandbox/execd:v1.0.21
          command: [ "/bin/sh", "-c" ]
          args:
            - |
              cp ./execd /opt/opensandbox/execd && 
              cp ./bootstrap.sh /opt/opensandbox/bootstrap.sh &&
              chmod +x /opt/opensandbox/execd &&
              chmod +x /opt/opensandbox/bootstrap.sh
          volumeMounts:
            - name: opensandbox-bin
              mountPath: /opt/opensandbox
      containers:
        - name: sandbox
          image: sandbox-registry.cn-zhangjiakou.cr.aliyuncs.com/opensandbox/code-interpreter:v1.1.0
          command:
          - "/bin/sh"
          - "-c"
          - |
            /opt/opensandbox/task-executor -listen-addr=0.0.0.0:5758 >/tmp/task-executor.log 2>&1
          env:
          - name: SANDBOX_MAIN_CONTAINER
            value: main
          - name: EXECD_ENVS
            value: /opt/opensandbox/.env
          - name: EXECD
            value: /opt/opensandbox/execd
          volumeMounts:
            - name: sandbox-storage
              mountPath: /var/lib/sandbox
            - name: opensandbox-bin
              mountPath: /opt/opensandbox
      tolerations:
        - operator: "Exists"
  capacitySpec:
    bufferMax: 3
    bufferMin: 1
    poolMax: 5
    poolMin: 0
```

Start the k8s OpenSandbox server:

```shell
uv pip install opensandbox-server

# replace with your k8s cluster config, kubeconfig etc.
opensandbox-server init-config ~/.sandbox.toml --example k8s
curl -o ~/batchsandbox-template.yaml https://raw.githubusercontent.com/opensandbox-group/OpenSandbox/main/server/opensandbox_server/examples/example.batchsandbox-template.yaml

opensandbox-server
```

### Create and access the Code Interpreter Sandbox (pool)

```shell
# Install OpenSandbox packages
uv pip install opensandbox opensandbox-code-interpreter

# Run the example (requires SANDBOX_DOMAIN / SANDBOX_API_KEY)
uv run python examples/code-interpreter/main_use_pool.py
```

### Pool example output

```text
=== Verify Environment Variable ===
[ENV Check] TEST_ENV value: test

[ENV Result] 'test'

=== Java example ===
[Java stdout] Hello from Java!

[Java stdout] 2 + 3 = 5

[Java result] 5

=== Go example ===
[Go stdout] Hello from Go!
3 + 4 = 7


=== TypeScript example ===
[TypeScript stdout] Hello from TypeScript!

[TypeScript stdout] sum = 6
```

## References

- [Source code on GitHub](https://github.com/opensandbox-group/OpenSandbox/tree/main/examples/code-interpreter)
