import { isPhotoLike, sized } from "./Photo";

describe("isPhotoLike", () => {
  it("accepts news-photo proportions at a usable size", () => {
    expect(isPhotoLike(1152, 648)).toBe(true); // 16:9
    expect(isPhotoLike(960, 640)).toBe(true); // 3:2
  });
  it("rejects small images, square logos and long banners", () => {
    expect(isPhotoLike(300, 200)).toBe(false);
    expect(isPhotoLike(800, 800)).toBe(false);
    expect(isPhotoLike(1500, 400)).toBe(false);
    expect(isPhotoLike(0, 0)).toBe(false);
  });
});

describe("sized", () => {
  it("asks Reuters' resizer for a smaller width and leaves other hosts alone", () => {
    expect(sized("https://www.reuters.com/resizer/v2/A.jpg?auth=x&smart=true&width=960", 480))
      .toBe("https://www.reuters.com/resizer/v2/A.jpg?auth=x&smart=true&width=480");
    expect(sized("https://cdn.arstechnica.net/a-1152x648.jpg", 480)).toBe("https://cdn.arstechnica.net/a-1152x648.jpg");
  });
});
