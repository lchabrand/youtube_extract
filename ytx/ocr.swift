// ocr.swift <image>…: text of each image with the macOS Vision framework, as one JSON object per line.
// Runs locally. Boxes are in pixels, origin at the top left.
import AppKit
import Foundation
import Vision

for path in CommandLine.arguments.dropFirst() {
    guard let image = NSImage(contentsOfFile: path),
          let cg = image.cgImage(forProposedRect: nil, context: nil, hints: nil) else { continue }
    let width = CGFloat(cg.width), height = CGFloat(cg.height)
    let request = VNRecognizeTextRequest()
    request.recognitionLevel = .accurate
    request.usesLanguageCorrection = false
    try? VNImageRequestHandler(cgImage: cg, options: [:]).perform([request])
    var items: [[String: Any]] = []
    for result in request.results ?? [] {
        guard let top = result.topCandidates(1).first else { continue }
        let b = result.boundingBox
        items.append(["t": top.string, "x": Int(b.minX * width), "y": Int((1 - b.maxY) * height),
                      "w": Int(b.width * width), "h": Int(b.height * height)])
    }
    let line: [String: Any] = ["file": path, "items": items]
    if let data = try? JSONSerialization.data(withJSONObject: line), let text = String(data: data, encoding: .utf8) {
        print(text)
    }
}
