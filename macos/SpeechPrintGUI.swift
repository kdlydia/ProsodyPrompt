import SwiftUI
import AppKit
import Foundation

// ============================================================================
// MARK: - App Entry
// ============================================================================

@main
struct SpeechPrintApp: App {
    var body: some Scene {
        WindowGroup {
            LandingView()
        }
        .windowResizability(.contentSize)
    }
}

// ============================================================================
// MARK: - Mode
// ============================================================================

enum SpeechPrintMode {
    case landing
    case install
    case createCorpus
}

enum ReleaseChannel: String, CaseIterable, Identifiable {
    case stable = "Stable"
    case dev = "Development"
    var id: String { rawValue }
    var subtitle: String {
        switch self {
        case .stable: return "Production-ready. Tested and stable."
        case .dev:    return "Latest features. May contain bugs."
        }
    }
}

struct LanguageModule: Identifiable, Hashable {
    let code: String
    let name: String
    var id: String { code }
}

let SUPPORTED_LANGUAGES: [LanguageModule] = [
    .init(code: "en", name: "English"),
    .init(code: "de", name: "German"),
    .init(code: "it", name: "Italian"),
    .init(code: "es", name: "Spanish"),
    .init(code: "fr", name: "French"),
    .init(code: "cs", name: "Czech"),
]

// ============================================================================
// MARK: - Landing View
// ============================================================================

struct LandingView: View {
    @State private var mode: SpeechPrintMode = .landing

    var body: some View {
        switch mode {
        case .landing:
            VStack(spacing: 24) {
                HStack(spacing: 12) {
                    Image(systemName: "waveform.path.ecg")
                        .font(.system(size: 48))
                        .foregroundColor(.blue)
                    VStack(alignment: .leading, spacing: 2) {
                        Text("SpeechPrint")
                            .font(.largeTitle)
                            .fontWeight(.bold)
                        Text("Linguistic Annotation Toolchain")
                            .font(.subheadline)
                            .foregroundColor(.secondary)
                    }
                }
                .padding(.top, 10)

                Divider()

                VStack(spacing: 14) {
                    Button {
                        mode = .install
                    } label: {
                        Label("Install SpeechPrint", systemImage: "arrow.down.circle")
                            .frame(maxWidth: .infinity)
                            .padding(.vertical, 6)
                    }
                    .buttonStyle(.borderedProminent)
                    .controlSize(.large)

                    Button {
                        mode = .createCorpus
                    } label: {
                        Label("Create New Corpus", systemImage: "folder.badge.plus")
                            .frame(maxWidth: .infinity)
                            .padding(.vertical, 6)
                    }
                    .buttonStyle(.bordered)
                    .controlSize(.large)
                }

                Button("Quit") {
                    NSApplication.shared.terminate(nil)
                }
                .buttonStyle(.borderless)
                .foregroundColor(.secondary)
            }
            .padding(40)
            .frame(width: 460)

        case .install:
            InstallView(onBack: { mode = .landing })

        case .createCorpus:
            CreateCorpusView(onBack: { mode = .landing })
        }
    }
}

// ============================================================================
// MARK: - Install View (multi-step)
// ============================================================================

struct InstallView: View {
    let onBack: () -> Void
    @State private var step: Int = 0
    @State private var channel: ReleaseChannel = .stable
    @State private var selectedLangs: Set<String> = ["en"]
    @State private var installLog: String = ""
    @State private var installing: Bool = false
    @State private var finished: Bool = false

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            HStack {
                Button(action: onBack) {
                    Label("Back", systemImage: "chevron.left")
                }
                .buttonStyle(.borderless)
                Spacer()
                Text("Step \(step + 1) of 4").foregroundColor(.secondary)
            }

            Divider()

            switch step {
            case 0: confirmationStep
            case 1: channelStep
            case 2: languageStep
            case 3: runStep
            default: EmptyView()
            }

            Spacer()

            HStack {
                Spacer()
                if step > 0 && !installing && !finished {
                    Button("Previous") { step -= 1 }
                }
                if step < 3 {
                    Button(step == 0 ? "Start" : "Next") {
                        step += 1
                    }
                    .buttonStyle(.borderedProminent)
                    .disabled(step == 2 && selectedLangs.isEmpty)
                } else if finished {
                    Button("Finish") { onBack() }
                        .buttonStyle(.borderedProminent)
                } else if !installing {
                    Button("Run Installer") { runInstaller() }
                        .buttonStyle(.borderedProminent)
                }
            }
        }
        .padding(28)
        .frame(width: 620, height: 560)
    }

    var confirmationStep: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Ready to Install?").font(.title2).fontWeight(.bold)
            Text("This will install:")
            Group {
                Text("• SpeechPrint toolchain (pipeline + CLI)")
                Text("• Audio tools: ffmpeg, Praat, libsndfile")
                Text("• ASR: WhisperX, PyTorch")
                Text("• Forced alignment: Montreal Forced Aligner")
                Text("• Acoustic models for selected languages")
            }
            .font(.system(.body, design: .default))
            Text("Requires: Internet connection, ~5GB disk space")
                .font(.footnote).foregroundColor(.secondary).padding(.top, 4)
        }
    }

    var channelStep: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Select Release Channel").font(.title2).fontWeight(.bold)
            ForEach(ReleaseChannel.allCases) { ch in
                Button {
                    channel = ch
                } label: {
                    HStack(alignment: .top) {
                        Image(systemName: channel == ch ? "largecircle.fill.circle" : "circle")
                            .foregroundColor(channel == ch ? .blue : .secondary)
                        VStack(alignment: .leading) {
                            Text(ch.rawValue).fontWeight(.semibold)
                            Text(ch.subtitle).font(.footnote).foregroundColor(.secondary)
                        }
                        Spacer()
                    }
                }
                .buttonStyle(.plain)
                .padding(10)
                .background(channel == ch ? Color.blue.opacity(0.08) : Color.clear)
                .cornerRadius(6)
            }
        }
    }

    var languageStep: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Select Language Modules").font(.title2).fontWeight(.bold)
            Text("Each language adds an MFA acoustic model + dictionary (~300 MB).")
                .font(.footnote).foregroundColor(.secondary)
            ScrollView {
                VStack(alignment: .leading, spacing: 6) {
                    ForEach(SUPPORTED_LANGUAGES) { lang in
                        Toggle(isOn: Binding(
                            get: { selectedLangs.contains(lang.code) },
                            set: { on in
                                if on { selectedLangs.insert(lang.code) }
                                else  { selectedLangs.remove(lang.code) }
                            })) {
                            Text("\(lang.name) (\(lang.code))")
                        }
                    }
                }
            }
            .frame(maxHeight: 220)
            Text("\(selectedLangs.count) module(s) selected · approx. \(selectedLangs.count * 300) MB")
                .font(.footnote).foregroundColor(.secondary)
        }
    }

    var runStep: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text(finished ? "✓ Installation Complete" : "Installing…")
                .font(.title2).fontWeight(.bold)
            ScrollView {
                Text(installLog.isEmpty ? "Press \"Run Installer\" to begin." : installLog)
                    .font(.system(.body, design: .monospaced))
                    .frame(maxWidth: .infinity, alignment: .leading)
            }
            .padding(8)
            .background(Color(NSColor.textBackgroundColor))
            .cornerRadius(4)
            if finished {
                Text("Restart your terminal, then:\n  speechprint new MyCorpus ~/Corpora/")
                    .font(.system(.footnote, design: .monospaced))
                    .foregroundColor(.secondary)
            }
        }
    }

    func runInstaller() {
        installing = true
        installLog = ""

        // Locate install_deps.sh next to the .app bundle, or in /Library/SpeechPrint
        let bundleScript = Bundle.main.bundlePath + "/Contents/Resources/install_deps.sh"
        let systemScript = "/Library/SpeechPrint/scripts/install_deps.sh"
        let script = FileManager.default.fileExists(atPath: bundleScript) ? bundleScript : systemScript

        guard FileManager.default.fileExists(atPath: script) else {
            installLog = "ERROR: install_deps.sh not found.\nLooked in:\n  \(bundleScript)\n  \(systemScript)"
            installing = false
            return
        }

        DispatchQueue.global(qos: .userInitiated).async {
            let task = Process()
            task.executableURL = URL(fileURLWithPath: "/bin/bash")
            task.arguments = [script, channel == .dev ? "dev" : "stable",
                              selectedLangs.sorted().joined(separator: ",")]
            let pipe = Pipe()
            task.standardOutput = pipe
            task.standardError = pipe

            pipe.fileHandleForReading.readabilityHandler = { handle in
                let data = handle.availableData
                if data.isEmpty { return }
                if let text = String(data: data, encoding: .utf8) {
                    DispatchQueue.main.async {
                        installLog.append(text)
                    }
                }
            }

            do {
                try task.run()
                task.waitUntilExit()
                DispatchQueue.main.async {
                    installing = false
                    finished = true
                }
            } catch {
                DispatchQueue.main.async {
                    installLog.append("ERROR: \(error.localizedDescription)\n")
                    installing = false
                }
            }
        }
    }
}

// ============================================================================
// MARK: - Create Corpus View
// ============================================================================

struct CreateCorpusView: View {
    let onBack: () -> Void
    @State private var name: String = "MyCorpus"
    @State private var location: String = NSHomeDirectory() + "/Corpora"
    @State private var language: String = "en"
    @State private var autoEnsemble: Bool = false
    @State private var withVSCode: Bool = true
    @State private var status: String = ""

    var previewPath: String {
        let safe = name.isEmpty ? "MyCorpus" : name
        return "\(location)/\(safe)"
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            HStack {
                Button(action: onBack) {
                    Label("Back", systemImage: "chevron.left")
                }
                .buttonStyle(.borderless)
                Spacer()
            }

            Text("New Corpus").font(.title2).fontWeight(.bold)

            VStack(alignment: .leading, spacing: 6) {
                Text("Corpus Name").font(.subheadline)
                TextField("MyCorpus", text: $name)
                    .textFieldStyle(.roundedBorder)
            }

            VStack(alignment: .leading, spacing: 6) {
                Text("Location").font(.subheadline)
                HStack {
                    TextField("~/Corpora", text: $location)
                        .textFieldStyle(.roundedBorder)
                    Button("Browse…") {
                        let panel = NSOpenPanel()
                        panel.canChooseDirectories = true
                        panel.canChooseFiles = false
                        panel.allowsMultipleSelection = false
                        if panel.runModal() == .OK, let url = panel.url {
                            location = url.path
                        }
                    }
                }
            }

            VStack(alignment: .leading, spacing: 6) {
                Text("Default Language").font(.subheadline)
                Picker("", selection: $language) {
                    ForEach(SUPPORTED_LANGUAGES) { l in
                        Text("\(l.name) (\(l.code))").tag(l.code)
                    }
                }
                .labelsHidden()
                .pickerStyle(.menu)
            }

            Toggle("Auto-ensemble after each annotate", isOn: $autoEnsemble)
            Toggle("Include VS Code configuration", isOn: $withVSCode)

            Text("Corpus will be created at:")
                .font(.footnote).foregroundColor(.secondary)
            Text(previewPath)
                .font(.system(.body, design: .monospaced))
                .textSelection(.enabled)

            if !status.isEmpty {
                Text(status)
                    .font(.footnote)
                    .foregroundColor(status.hasPrefix("✓") ? .green : .red)
            }

            Spacer()

            HStack {
                Spacer()
                Button("Cancel") { onBack() }
                Button("Create Corpus") { createCorpus() }
                    .buttonStyle(.borderedProminent)
                    .disabled(name.isEmpty)
            }
        }
        .padding(28)
        .frame(width: 560, height: 540)
    }

    func createCorpus() {
        // Prefer a system-installed speechprint CLI; fall back to bundled script.
        var cmd = ["speechprint", "new", name, location, "--language", language]
        if autoEnsemble { cmd.append("--auto-ensemble") }
        if !withVSCode  { cmd.append("--no-vscode") }

        DispatchQueue.global(qos: .userInitiated).async {
            let task = Process()
            task.executableURL = URL(fileURLWithPath: "/usr/bin/env")
            task.arguments = cmd
            let pipe = Pipe()
            task.standardOutput = pipe
            task.standardError = pipe

            do {
                try task.run()
                task.waitUntilExit()
                let data = pipe.fileHandleForReading.readDataToEndOfFile()
                let output = String(data: data, encoding: .utf8) ?? ""
                DispatchQueue.main.async {
                    if task.terminationStatus == 0 {
                        status = "✓ Corpus created at \(previewPath)"
                    } else {
                        status = "✗ Failed: \(output.split(separator: "\n").last ?? "unknown error")"
                    }
                }
            } catch {
                DispatchQueue.main.async {
                    status = "✗ Could not run speechprint: \(error.localizedDescription)"
                }
            }
        }
    }
}
