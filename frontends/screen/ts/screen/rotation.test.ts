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

  it("retargets body selectors to the stage for any non-zero rotation, keeps units at 180", () => {
    setRotation(180);
    expect(adaptCss("body { background: blue; }\nhtml body, .x { color: red; } .y { width: 1vh }")).toBe(
      "#main-container { background: blue; }\n#main-container, .x { color: red; } .y { width: 1vh }",
    );
    // a declaration value that merely contains the word is left alone
    expect(adaptCss(".z { font-family: body-font; }")).toBe(".z { font-family: body-font; }");
  });
});
