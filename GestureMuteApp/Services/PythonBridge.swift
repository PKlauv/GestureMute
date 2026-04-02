import Foundation
import os

/// Manages the Python engine subprocess and JSON-line IPC.
@Observable
final class PythonBridge {
    private(set) var isRunning = false
    private var process: Process?
    private var stdinPipe = Pipe()
    private var stdoutPipe = Pipe()
    private var stderrPipe = Pipe()
    private var outputBuffer = Data()
    private let logger = Logger(subsystem: "com.gesturemute.app", category: "PythonBridge")

    /// Callback for each parsed event from Python.
    var onEvent: ((String, [String: Any]) -> Void)?

    /// Launch the Python engine subprocess.
    func launch() {
        guard !isRunning else { return }

        let bundle = Bundle.main
        guard let engineURL = bundle.url(
            forResource: "gesturemute_engine",
            withExtension: nil,
            subdirectory: "python_engine"
        ) else {
            // Fallback: try to find bridge_main.py for development
            launchDevelopmentMode()
            return
        }

        let process = Process()
        process.executableURL = engineURL
        process.environment = [
            "OPENCV_LOG_LEVEL": "SILENT",
        ]
        configureProcess(process)
    }

    /// Development mode: run bridge_main.py directly with system Python.
    private func launchDevelopmentMode() {
        // Find the project root by walking up from the app bundle
        let projectRoot = findProjectRoot()
        let bridgeScript = projectRoot.appendingPathComponent("bridge_main.py")
        let venvPython = projectRoot.appendingPathComponent("venv/bin/python3")

        let pythonPath: URL
        if FileManager.default.fileExists(atPath: venvPython.path) {
            pythonPath = venvPython
        } else {
            pythonPath = URL(fileURLWithPath: "/usr/bin/python3")
        }

        guard FileManager.default.fileExists(atPath: bridgeScript.path) else {
            logger.error("Cannot find bridge_main.py at \(bridgeScript.path)")
            return
        }

        let process = Process()
        process.executableURL = pythonPath
        process.arguments = [bridgeScript.path]
        process.currentDirectoryURL = projectRoot
        process.environment = [
            "OPENCV_LOG_LEVEL": "SILENT",
            "PYTHONPATH": projectRoot.path,
        ]
        configureProcess(process)
    }

    private func findProjectRoot() -> URL {
        let fm = FileManager.default
        let marker = "bridge_main.py"

        // Derive project root from this source file's compile-time path:
        // .../GestureMuteApp/Services/PythonBridge.swift → walk up 3 levels
        let thisFile = URL(fileURLWithPath: #filePath)
        let fromSource = thisFile
            .deletingLastPathComponent()  // Services/
            .deletingLastPathComponent()  // GestureMuteApp/
            .deletingLastPathComponent()  // project root
        if fm.fileExists(atPath: fromSource.appendingPathComponent(marker).path) {
            return fromSource
        }

        // Fallback: current working directory
        let cwd = URL(fileURLWithPath: fm.currentDirectoryPath)
        return cwd
    }

    private func configureProcess(_ process: Process) {
        stdinPipe = Pipe()
        stdoutPipe = Pipe()
        stderrPipe = Pipe()

        process.standardInput = stdinPipe
        process.standardOutput = stdoutPipe
        process.standardError = stderrPipe

        // Read stdout asynchronously (JSON events from Python)
        stdoutPipe.fileHandleForReading.readabilityHandler = { [weak self] handle in
            let data = handle.availableData
            guard !data.isEmpty else {
                // EOF — process exited
                DispatchQueue.main.async {
                    self?.isRunning = false
                }
                return
            }
            self?.handleStdoutData(data)
        }

        // Read stderr for logging
        stderrPipe.fileHandleForReading.readabilityHandler = { [weak self] handle in
            let data = handle.availableData
            if let text = String(data: data, encoding: .utf8), !text.isEmpty {
                self?.logger.debug("Python: \(text)")
            }
        }

        process.terminationHandler = { [weak self] _ in
            DispatchQueue.main.async {
                self?.isRunning = false
                self?.logger.info("Python process terminated")
            }
        }

        do {
            try process.run()
            self.process = process
            isRunning = true
            logger.info("Python engine launched (PID: \(process.processIdentifier))")
        } catch {
            logger.error("Failed to launch Python engine: \(error)")
        }
    }

    /// Send a command to the Python engine.
    func send(_ command: IPCCommand) {
        guard isRunning, let data = command.encode() else { return }
        stdinPipe.fileHandleForWriting.write(data)
    }

    /// Terminate the Python subprocess.
    func terminate() {
        guard isRunning, let process else { return }
        send(.shutdown)
        // Give it a moment to shut down gracefully
        DispatchQueue.global().asyncAfter(deadline: .now() + 1) { [weak self] in
            if process.isRunning {
                process.terminate()
                self?.logger.info("Python process force-terminated")
            }
        }
    }

    // MARK: - Stdout Parsing

    private func handleStdoutData(_ data: Data) {
        // Guard against runaway buffer growth (e.g. Python crash spewing garbage)
        if outputBuffer.count + data.count > 4 * 1024 * 1024 {
            logger.error("stdout buffer overflow (\(self.outputBuffer.count) bytes) — discarding and terminating engine")
            outputBuffer.removeAll()
            terminate()
            return
        }
        outputBuffer.append(data)

        // Split on newlines and parse each complete JSON line
        while let newlineIndex = outputBuffer.firstIndex(of: 0x0A) {
            let lineData = outputBuffer[outputBuffer.startIndex..<newlineIndex]
            outputBuffer = Data(outputBuffer[outputBuffer.index(after: newlineIndex)...])

            guard !lineData.isEmpty else { continue }

            do {
                if let json = try JSONSerialization.jsonObject(with: lineData) as? [String: Any],
                   let type = json["type"] as? String {
                    let payload = json["payload"] as? [String: Any] ?? [:]
                    DispatchQueue.main.async { [weak self] in
                        self?.onEvent?(type, payload)
                    }
                }
            } catch {
                logger.error("Failed to parse JSON from Python: \(error)")
            }
        }
    }

    deinit {
        terminate()
        stdoutPipe.fileHandleForReading.readabilityHandler = nil
        stderrPipe.fileHandleForReading.readabilityHandler = nil
    }
}
