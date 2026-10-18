import { describe, expect, it, beforeEach } from "vitest";
import { adaptCss, adaptHtml, containerGeometry, getRotation, setRotation } from "./rotation";

describe("rotation", () => {
  beforeEach(() => setRotation(0));

  it("normalizes to 0/90/180/270 (-90 is 270)", () => {
    setRotation(-90);
    expect(getRotation()).toBe(270);
    setRotation(450);
    expect(getRotation()).toBe(90);
    setRotation(45);
    expect(getRotation()).toBe(90);
    setRotation(0);
    expect(getRotation()).toBe(0);
  });

  it("leaves everything alone at 0 degrees", () => {
    const css = "body { background: red; } .a { width: 10vh; top: 5vw; }";
    expect(adaptCss(css)).toBe(css);
    expect(adaptHtml('<i style="font-size:5vh">x</i>')).toBe('<i style="font-size:5vh">x</i>');
    expect(containerGeometry({ top: 1, left: 2, width: 3, height: 4 })).toEqual({
      top: "1vh", left: "2vw", width: "3vw", height: "4vh",
    });
  });

  it("swaps vh/vw axes for quarter turns, in CSS, HTML and container geometry", () => {
    setRotation(90);
    expect(adaptCss(".a { width: 10vh; top: 5vw; height: calc(100dvh - 2.5vw); }")).toBe(
      ".a { width: 10vw; top: 5vh; height: calc(100dvw - 2.5vh); }",
    );
    expect(adaptHtml('<i style="font-size:5vh;left:-.5vw">x</i>')).toBe('<i style="font-size:5vw;left:-.5vh">x</i>');
    expect(containerGeometry({ top: 1, left: 2, width: 3, height: 4 })).toEqual({
      top: "1vw", left: "2vh", width: "3vh", height: "4vw",
    });
    setRotation(270);
    expect(adaptCss(".a { width: 10vh }")).toBe(".a { width: 10vw }");
  });

  it("does not touch vmin/vmax or non-unit text", () => {
    setRotation(90);
    expect(adaptCss(".a { width: 10vmin; content: 'vh'; font-family: Overhead; }")).toBe(
      ".a { width: 10vmin; content: 'vh'; font-family: Overhead; }",
    );
  });

  it("leaves url(), strings, comments and @media conditions alone, but swaps inside var() fallbacks", () => {
    setRotation(90);
    expect(adaptCss(".a { background: url(img10vh.png) 0 5vh; }")).toBe(".a { background: url(img10vh.png) 0 5vw; }");
    expect(adaptCss('.a { background: url("a 3vw.png"); content: "5vw"; top: 2vh }')).toBe(
      '.a { background: url("a 3vw.png"); content: "5vw"; top: 2vw }',
    );
    expect(adaptCss("/* 9vh */ .a { top: 9vh !important }")).toBe("/* 9vh */ .a { top: 9vw !important }");
    expect(adaptCss("@media (min-width: 100vw) { .a { top: 2vh } } .b { left: 1vw }")).toBe(
      "@media (min-width: 100vw) { .a { top: 2vw } } .b { left: 1vh }",
    );
    expect(adaptCss(".a { width: var(--a, 3vw) }")).toBe(".a { width: var(--a, 3vh) }");
  });

  it("swaps units in HTML only inside style attributes and <style> blocks", () => {
    setRotation(90);
    expect(adaptHtml('<p>Height 10vh</p><a href="/x10vh">go</a><div style="top:5vh;background:url(a10vw.png)">x</div>')).toBe(
      '<p>Height 10vh</p><a href="/x10vh">go</a><div style="top:5vw;background:url(a10vw.png)">x</div>',
    );
    expect(adaptHtml("<style>.a{width:10vh}</style><script>var h='10vh'</script><i style='left:2vw'>x</i>")).toBe(
      "<style>.a{width:10vw}</style><script>var h='10vh'</script><i style='left:2vh'>x</i>",
    );
  });

  it("retargets body selectors to the stage for any non-zero rotation, keeps units at 180", () => {
    setRotation(180);
    expect(adaptCss("body { background: blue; }\nhtml body, .x { color: red; } .y { width: 1vh }")).toBe(
      "#main-container { background: blue; }\n#main-container, .x { color: red; } .y { width: 1vh }",
    );
    // a declaration value that merely contains the word is left alone
    expect(adaptCss(".z { font-family: body-font; }")).toBe(".z { font-family: body-font; }");
  });
});
