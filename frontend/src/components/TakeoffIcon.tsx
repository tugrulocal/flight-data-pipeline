import airplaneIcon from "../icons/airplane.png";

interface TakeoffIconProps {
  className?: string;
}

export function TakeoffIcon({ className }: TakeoffIconProps) {
  return (
    <img
      className={className}
      src={airplaneIcon}
      alt=""
      aria-hidden="true"
    />
  );
}
