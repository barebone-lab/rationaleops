import { Composition } from "remotion";
import { RationaleOpsVideo, VIDEO_DURATION_FRAMES } from "./Composition";
import "./index.css";

export const RemotionRoot: React.FC = () => {
  return (
    <Composition
      id="RationaleOpsDemo"
      component={RationaleOpsVideo}
      durationInFrames={VIDEO_DURATION_FRAMES}
      fps={30}
      width={1920}
      height={1080}
      defaultProps={{}}
    />
  );
};
