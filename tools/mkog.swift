import Cocoa
import CoreText

// SQORE OGカード再生成: 1200x630
let W = 1200, H = 630
let iconPath = NSString(string: "~/Developer/SQORE/SQORE/Assets.xcassets/AppIcon.appiconset/Icon-1024.png").expandingTildeInPath
let outPath = CommandLine.arguments.count > 1 ? CommandLine.arguments[1] : NSString(string: "~/Desktop/og_new.png").expandingTildeInPath

let cs = CGColorSpaceCreateDeviceRGB()
guard let ctx = CGContext(data: nil, width: W, height: H, bitsPerComponent: 8, bytesPerRow: 0,
                          space: cs, bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue) else { exit(1) }
// 左上原点にする
ctx.translateBy(x: 0, y: CGFloat(H))
ctx.scaleBy(x: 1, y: -1)

// --- 背景グラデーション(元画像の四隅の実測値をバイリニアで再現) -----------------
// 元画像は色が x,y の一次式になっているので、ピクセル単位でそのまま再現する
let TL = (0.0, 163.0, 223.0), TR = (0.0, 120.0, 185.0), BL = (0.0, 151.0, 213.0)
if let buf = ctx.data {
    let p = buf.bindMemory(to: UInt8.self, capacity: ctx.bytesPerRow * H)
    for y in 0..<H {
        let fy = Double(y) / Double(H)
        for x in 0..<W {
            let fx = Double(x) / Double(W)
            let o = y * ctx.bytesPerRow + x * 4
            p[o + 0] = UInt8(max(0, min(255, TL.0 + (TR.0 - TL.0) * fx + (BL.0 - TL.0) * fy)))
            p[o + 1] = UInt8(max(0, min(255, TL.1 + (TR.1 - TL.1) * fx + (BL.1 - TL.1) * fy)))
            p[o + 2] = UInt8(max(0, min(255, TL.2 + (TR.2 - TL.2) * fx + (BL.2 - TL.2) * fy)))
            p[o + 3] = 255
        }
    }
}

// --- アイコン ---------------------------------------------------------------
let iconRect = CGRect(x: 110, y: 165, width: 300, height: 300)
let radius: CGFloat = 67
if let src = NSImage(contentsOfFile: iconPath),
   let cg = src.cgImage(forProposedRect: nil, context: nil, hints: nil) {
    ctx.saveGState()
    ctx.setShadow(offset: CGSize(width: 0, height: -10), blur: 28,
                  color: CGColor(red: 0, green: 0.12, blue: 0.25, alpha: 0.35))
    ctx.beginPath()
    ctx.addPath(CGPath(roundedRect: iconRect, cornerWidth: radius, cornerHeight: radius, transform: nil))
    ctx.setFillColor(CGColor(red: 0, green: 0.4, blue: 0.8, alpha: 1))
    ctx.fillPath()
    ctx.restoreGState()

    ctx.saveGState()
    ctx.addPath(CGPath(roundedRect: iconRect, cornerWidth: radius, cornerHeight: radius, transform: nil))
    ctx.clip()
    ctx.saveGState()
    ctx.translateBy(x: 0, y: iconRect.midY * 2)
    ctx.scaleBy(x: 1, y: -1)          // 画像は上下反転して描く
    ctx.draw(cg, in: iconRect)
    ctx.restoreGState()
    ctx.restoreGState()
} else {
    FileHandle.standardError.write("icon load failed\n".data(using: .utf8)!)
    exit(1)
}

// --- テキスト ---------------------------------------------------------------
func font(_ name: String, _ size: CGFloat) -> CTFont { CTFontCreateWithName(name as CFString, size, nil) }

func draw(_ s: String, x: CGFloat, top: CGFloat, font f: CTFont, color: CGColor) -> CGFloat {
    let attr = NSAttributedString(string: s, attributes: [
        .font: f, .foregroundColor: color,
    ])
    let line = CTLineCreateWithAttributedString(attr)
    let bounds = CTLineGetBoundsWithOptions(line, .useOpticalBounds)
    // top = 文字の上端の、画面上端からの距離
    ctx.saveGState()
    ctx.translateBy(x: x - bounds.minX, y: top + bounds.maxY)
    ctx.scaleBy(x: 1, y: -1)
    ctx.textPosition = .zero
    CTLineDraw(line, ctx)
    ctx.restoreGState()
    return CTLineGetTypographicBounds(line, nil, nil, nil)
}

let white = CGColor(red: 1, green: 1, blue: 1, alpha: 1)
let yellow = CGColor(red: 255/255, green: 198/255, blue: 90/255, alpha: 1)

// SQORE (実測: x=482, 上端152 下端228)
_ = draw("SQORE", x: 480, top: 129, font: font("HelveticaNeue-Bold", 96), color: white)
// 1行目 (実測: x=485, 上端303 下端354)
_ = draw("ゴルフの握りを", x: 479, top: 302, font: font("HiraginoSans-W6", 53), color: white)
// 2行目 (実測: x=486, 上端391 下端443)
let w1 = draw("自動計算", x: 479, top: 390, font: font("HiraginoSans-W6", 54), color: yellow)
_ = draw("で超簡単に", x: 479 + w1 + 18, top: 390, font: font("HiraginoSans-W6", 54), color: white)
// サブ (実測: x=481, 上端489 下端516)
_ = draw("オリンピック・ラスベガス・ナッソーなど多数対応", x: 479, top: 488, font: font("HiraginoSans-W3", 28), color: white)

guard let img = ctx.makeImage() else { exit(1) }
let rep = NSBitmapImageRep(cgImage: img)
guard let png = rep.representation(using: .png, properties: [:]) else { exit(1) }
try! png.write(to: URL(fileURLWithPath: outPath))
print("saved \(outPath)")
